from typing import List, Optional, Tuple
import json
from pathlib import Path as FSPath
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session, select, or_
from app.database import get_session
from app.models import Submission, Course, User, UC
from app.schemas import SubmissionCreate, SubmissionUpdateGrade, SubmissionResponse
from app.core.helper import status_Grade, status_Course
from app.api.auth import get_current_user

# Используем абсолютный путь для CONTENT_ROOT
CONTENT_ROOT = FSPath(__file__).parent.parent.parent / "content"
CONTENT_ROOT = CONTENT_ROOT.resolve()
COURSE_CONTENT_DIR = CONTENT_ROOT / "courses"


def _load_course_content(course: Course) -> dict:
    """
    Читает JSON-файл курса.
    Путь берется из course.URL если это путь к файлу, иначе из content/courses/{id}.json.
    """
    # если URL указывает на локальный файл
    if course.URL and FSPath(course.URL).exists():
        file_path = FSPath(course.URL)
    else:
        file_path = COURSE_CONTENT_DIR / f"{course.id}.json"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл курса не найден")

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Некорректный JSON курса")

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _get_task_from_course(course: Course, topic_key: str, lecture_key: str, task_key: str) -> Optional[dict]:
    """Получить информацию о задаче из курса"""
    try:
        content = _load_course_content(course)
        if topic_key in content and "lectures" in content[topic_key]:
            if lecture_key in content[topic_key]["lectures"]:
                lecture = content[topic_key]["lectures"][lecture_key]
                if "tasks" in lecture and task_key in lecture["tasks"]:
                    return lecture["tasks"][task_key]
    except Exception:
        pass
    return None


def _check_answer(task: dict, user_answer: str) -> Tuple[bool, Optional[int]]:
    """
    Проверяет ответ ученика и возвращает (правильность, оценка 1-5)
    Для manual задач всегда возвращает (False, None) - требует ручной проверки
    """
    task_type = task.get("type", "manual")
    
    if task_type == "manual":
        # Развернутый ответ требует ручной проверки
        return (False, None)
    
    elif task_type == "single_choice":
        # Правильный ответ - индекс (0-based), но может быть сохранен как число или строка
        correct_answer = task.get("correct_answer")
        
        # Логируем для отладки
        print(f"Проверка single_choice: correct_answer={correct_answer}, type={type(correct_answer)}, user_answer={user_answer}, task={task}")
        
        if correct_answer is None:
            print(f"Ошибка: correct_answer is None для задачи single_choice")
            return (False, None)
        
        try:
            # Преобразуем в число, если это строка
            if isinstance(correct_answer, str):
                correct_answer = int(correct_answer)
            else:
                correct_answer = int(correct_answer)
            
            # Ответ ученика - это индекс (0-based), который он выбрал
            user_choice = int(user_answer)
            
            print(f"Сравнение: user_choice={user_choice}, correct_answer={correct_answer}")
            
            # Сравниваем индексы
            if user_choice == correct_answer:
                print(f"Правильный ответ! Оценка: 5")
                return (True, 5)  # Правильно - 5 баллов
            else:
                print(f"Неправильный ответ. Оценка: 1")
                return (False, 1)  # Неправильно - 1 балл
        except (ValueError, TypeError) as e:
            # Логируем ошибку для отладки
            print(f"Ошибка проверки single_choice: correct_answer={correct_answer}, user_answer={user_answer}, error={e}")
            return (False, 1)
    
    elif task_type == "multiple_choice":
        # Правильный ответ - JSON массив индексов
        correct_answer_str = task.get("correct_answer")
        if not correct_answer_str:
            return (False, None)
        
        try:
            # Парсим правильные ответы
            if isinstance(correct_answer_str, str):
                correct_answers = json.loads(correct_answer_str)
            else:
                correct_answers = correct_answer_str
            
            if not isinstance(correct_answers, list):
                return (False, None)
            
            # Парсим ответ ученика
            user_answers = json.loads(user_answer)
            if not isinstance(user_answers, list):
                return (False, 1)
            
            # Сортируем для сравнения
            correct_answers_sorted = sorted(correct_answers)
            user_answers_sorted = sorted(user_answers)
            
            if correct_answers_sorted == user_answers_sorted:
                return (True, 5)  # Все правильно - 5 баллов
            else:
                # Частично правильно - считаем процент
                correct_count = len(set(correct_answers) & set(user_answers))
                total_correct = len(correct_answers)
                if total_correct == 0:
                    return (False, 1)
                
                percentage = correct_count / total_correct
                if percentage >= 0.8:
                    return (False, 4)  # Почти правильно - 4 балла
                elif percentage >= 0.5:
                    return (False, 3)  # Частично правильно - 3 балла
                else:
                    return (False, 2)  # Мало правильных - 2 балла
        except (json.JSONDecodeError, ValueError, TypeError):
            return (False, 1)
    
    elif task_type == "text_answer":
        # Правильный ответ - строка (регистронезависимое сравнение)
        correct_answer = task.get("correct_answer", "").strip().lower()
        user_answer_clean = user_answer.strip().lower()
        
        if not correct_answer:
            return (False, None)
        
        if user_answer_clean == correct_answer:
            return (True, 5)  # Правильно - 5 баллов
        else:
            # Проверяем частичное совпадение
            if correct_answer in user_answer_clean or user_answer_clean in correct_answer:
                return (False, 3)  # Частично правильно - 3 балла
            else:
                return (False, 1)  # Неправильно - 1 балл
    
    return (False, None)


@router.post("", response_model=SubmissionResponse)
def create_or_update_submission(
    submission: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Студент отправляет решение по задаче.
    Если для этой задачи уже есть отправка от текущего пользователя — обновляем её и сбрасываем статус на not_verified.
    """
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Неизвестный пользователь")

    # Проверяем существование курса
    course = session.get(Course, submission.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    existing = session.exec(
        select(Submission).where(
            Submission.course_id == submission.course_id,
            Submission.topic_key == submission.topic_key,
            Submission.lecture_key == submission.lecture_key,
            Submission.task_key == submission.task_key,
            Submission.user_id == current_user.id,
        )
    ).first()

    # Получаем информацию о задаче для автоматической проверки
    task_info = _get_task_from_course(course, submission.topic_key, submission.lecture_key, submission.task_key)
    
    # Автоматическая проверка для задач без развернутого ответа
    auto_checked = False
    auto_grade = None
    if task_info and task_info.get("type") != "manual":
        is_correct, grade = _check_answer(task_info, submission.answer)
        if grade is not None:
            auto_checked = True
            auto_grade = grade
    
    if existing:
        existing.answer = submission.answer
        if auto_checked:
            # Автоматически проверено
            existing.status = status_Grade.rated
            existing.grade = auto_grade
            existing.teacher_comment = "Автоматическая проверка"
        else:
            # Требует ручной проверки
            existing.status = status_Grade.not_verified
            existing.grade = None
            existing.teacher_comment = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    new_submission = Submission(
        course_id=submission.course_id,
        topic_key=submission.topic_key,
        lecture_key=submission.lecture_key,
        task_key=submission.task_key,
        user_id=current_user.id,
        answer=submission.answer,
        status=status_Grade.rated if auto_checked else status_Grade.not_verified,
        grade=auto_grade,
        teacher_comment="Автоматическая проверка" if auto_checked else None,
    )
    session.add(new_submission)
    session.commit()
    session.refresh(new_submission)
    return new_submission


@router.get("/mine", response_model=List[SubmissionResponse])
def list_my_submissions(
    course_id: Optional[int] = Query(None),
    lecture_key: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Неизвестный пользователь")

    query = select(Submission).where(Submission.user_id == current_user.id)
    if course_id is not None:
        query = query.where(Submission.course_id == course_id)
    if lecture_key is not None:
        query = query.where(Submission.lecture_key == lecture_key)

    submissions = session.exec(query).all()
    return submissions


@router.get("/review", response_model=List[SubmissionResponse])
def list_for_review(
    course_id: Optional[int] = Query(None),
    lecture_key: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Преподаватель просматривает все отправки по своим курсам.
    """
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Неизвестный пользователь")

    # Разрешаем только преподавателю, который создал курс
    base_query = select(Submission)
    if course_id is not None:
        course = session.get(Course, course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Курс не найден")
        if course.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Нет прав просматривать отправки")
        base_query = base_query.where(Submission.course_id == course_id)
        
        # Для публичных курсов показываем только зачисленных учеников
        if course.status == status_Course.public:
            enrolled_ucs = session.exec(
                select(UC).where(UC.course_id == course_id)
            ).all()
            enrolled_user_ids = {uc.user_id for uc in enrolled_ucs}
            if enrolled_user_ids:
                base_query = base_query.where(Submission.user_id.in_(enrolled_user_ids))
            else:
                # Если никто не зачислен, возвращаем пустой список
                return []
    else:
        # Выбираем только курсы, созданные преподавателем
        teacher_courses = session.exec(
            select(Course).where(Course.creator_id == current_user.id)
        ).all()
        teacher_course_ids = {c.id for c in teacher_courses if c.id is not None}
        
        if not teacher_course_ids:
            return []
        
        # Для публичных курсов фильтруем по зачисленным
        public_course_ids = {c.id for c in teacher_courses if c.status == status_Course.public}
        if public_course_ids:
            enrolled_ucs = session.exec(
                select(UC).where(UC.course_id.in_(public_course_ids))
            ).all()
            enrolled_user_ids = {uc.user_id for uc in enrolled_ucs}
            
            # Создаем условие: либо курс не публичный, либо пользователь зачислен
            conditions = []
            for cid in teacher_course_ids:
                course_obj = next((c for c in teacher_courses if c.id == cid), None)
                if course_obj and course_obj.status == status_Course.public:
                    # Для публичных - только зачисленные
                    if enrolled_user_ids:
                        conditions.append(
                            (Submission.course_id == cid) & (Submission.user_id.in_(enrolled_user_ids))
                        )
                else:
                    # Для приватных и draft - все
                    conditions.append(Submission.course_id == cid)
            
            if conditions:
                base_query = base_query.where(or_(*conditions))
            else:
                return []
        else:
            # Нет публичных курсов - показываем все
            base_query = base_query.where(Submission.course_id.in_(teacher_course_ids))

    if lecture_key is not None:
        base_query = base_query.where(Submission.lecture_key == lecture_key)

    submissions = session.exec(base_query).all()
    
    # Загружаем имена пользователей для удобства
    user_ids = {s.user_id for s in submissions if s.user_id is not None}
    users = {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all() if u.id is not None}
    
    # Добавляем имена пользователей к submissions (через расширение схемы)
    result = []
    for sub in submissions:
        sub_dict = {
            "id": sub.id,
            "course_id": sub.course_id,
            "topic_key": sub.topic_key,
            "lecture_key": sub.lecture_key,
            "task_key": sub.task_key,
            "user_id": sub.user_id,
            "answer": sub.answer,
            "status": sub.status,
            "grade": sub.grade,
            "teacher_comment": sub.teacher_comment,
        }
        # Добавляем имя пользователя, если доступно
        if sub.user_id and sub.user_id in users:
            sub_dict["user_name"] = users[sub.user_id].name
        result.append(sub_dict)
    
    return result


@router.put("/{submission_id}/grade", response_model=SubmissionResponse)
def grade_submission(
    submission_id: int = Path(...),
    payload: SubmissionUpdateGrade = ...,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Преподаватель оценивает отправку: статус -> rated, grade, comment.
    Если это автопроверенный ответ и преподаватель его просматривает без изменений,
    можно оставить статус rated, но изменить комментарий.
    """
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Отправка не найдена")

    course = session.get(Course, submission.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    if course.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав оценивать отправку")

    # Если это автопроверенный ответ и преподаватель просто просматривает,
    # можно изменить комментарий, чтобы отметить как просмотренное
    is_auto_checked = submission.status == status_Grade.rated and submission.teacher_comment == "Автоматическая проверка"
    
    if is_auto_checked:
        # Автопроверенный ответ - преподаватель может просмотреть и изменить
        if payload.grade is not None:
            submission.grade = payload.grade
        # Если преподаватель добавил комментарий, используем его
        if payload.teacher_comment and payload.teacher_comment != "Автоматическая проверка":
            submission.teacher_comment = payload.teacher_comment
        # Если комментарий пустой, оставляем автокомментарий (не меняем)
        elif payload.teacher_comment == "":
            submission.teacher_comment = "Автоматическая проверка"
    else:
        # Обычная проверка
        submission.status = payload.status
        submission.grade = payload.grade
        submission.teacher_comment = payload.teacher_comment
    
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission

