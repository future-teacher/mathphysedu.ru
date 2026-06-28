from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os
from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver


class Teacher(models.Model):
    """Модель преподавателя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)
    telegram = models.CharField(max_length=100, verbose_name='Telegram', blank=True)
    telegram_chat_id = models.BigIntegerField(
        null=True, blank=True, verbose_name='Telegram Chat ID',
        help_text='Числовой ID чата для отправки уведомлений (заполняется автоматически)'
    )
    bio = models.TextField(verbose_name='О преподавателе', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"
    
    class Meta:
        verbose_name = 'Преподаватель'
        verbose_name_plural = 'Преподаватели'


class Student(models.Model):
    """Модель ученика"""
    
    EXAM_TYPE_CHOICES = [
        ('oge_math', 'ОГЭ по математике'),
        ('oge_physics', 'ОГЭ по физике'),
        ('ege_math', 'ЕГЭ по математике'),
        ('ege_physics', 'ЕГЭ по физике'),
        ('improvement', 'Повышение успеваемости'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='students', verbose_name='Преподаватель')
    
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    class_name = models.CharField(max_length=50, verbose_name='Класс')
    
    telegram_username = models.CharField(max_length=100, verbose_name='Telegram @username',
                                        help_text='Начинается с @')
    telegram_chat_id = models.BigIntegerField(
        null=True, blank=True, verbose_name='Telegram Chat ID',
        help_text='Числовой ID чата ученика (заполняется автоматически после /start)'
    )
    parent_telegram = models.CharField(max_length=100, verbose_name='Telegram родителя',
                                      blank=True, help_text='Начинается с @')
    parent_name = models.CharField(max_length=200, verbose_name='Имя родителя')
    
    school = models.CharField(max_length=200, verbose_name='Школа')
    
    exam_types = models.CharField(
        max_length=200,
        verbose_name='Типы подготовки',
        help_text='Выберите типы подготовки (можно несколько)',
        default='',
        blank=True
    )
    
    current_level = models.CharField(max_length=100, verbose_name='Текущий уровень')
    weak_topics = models.TextField(verbose_name='Слабые темы')
    start_date = models.DateField(verbose_name='Дата начала занятий')
    
    exam_date_oge_math = models.DateField(null=True, blank=True, verbose_name='Дата ОГЭ по математике')
    exam_date_oge_physics = models.DateField(null=True, blank=True, verbose_name='Дата ОГЭ по физике')
    exam_date_ege_math = models.DateField(null=True, blank=True, verbose_name='Дата ЕГЭ по математике')
    exam_date_ege_physics = models.DateField(null=True, blank=True, verbose_name='Дата ЕГЭ по физике')
    
    notes = models.TextField(verbose_name='Заметки', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.class_name}"
    
    def get_exam_types_display(self):
        """Получить отображаемые названия выбранных типов подготовки"""
        exam_type_dict = dict(self.EXAM_TYPE_CHOICES)
        if not self.exam_types:
            return []
        selected_types = [et.strip() for et in self.exam_types.split(',') if et.strip()]
        return [exam_type_dict.get(et, et) for et in selected_types]
    
    def get_exam_types_list(self):
        """Получить список выбранных типов подготовки"""
        if not self.exam_types:
            return []
        return [et.strip() for et in self.exam_types.split(',') if et.strip()]
    
    def get_active_exam_dates(self):
        """Получить активные даты экзаменов на основе выбранных типов подготовки"""
        active_dates = []
        selected_types = self.get_exam_types_list()
        
        exam_mapping = {
            'oge_math': ('ОГЭ по математике', self.exam_date_oge_math),
            'oge_physics': ('ОГЭ по физике', self.exam_date_oge_physics),
            'ege_math': ('ЕГЭ по математике', self.exam_date_ege_math),
            'ege_physics': ('ЕГЭ по физике', self.exam_date_ege_physics),
        }
        
        for exam_type, (exam_name, exam_date) in exam_mapping.items():
            if exam_type in selected_types and exam_date:
                active_dates.append((exam_name, exam_date))
        
        return active_dates
    
    def has_active_exams(self):
        """Проверить, есть ли активные экзамены"""
        return len(self.get_active_exam_dates()) > 0
    
    @property
    def has_math(self):
        """Проверить, занимается ли ученик математикой"""
        return any(t in self.get_exam_types_list() for t in ['oge_math', 'ege_math'])
    
    @property
    def has_physics(self):
        """Проверить, занимается ли ученик физикой"""
        return any(t in self.get_exam_types_list() for t in ['oge_physics', 'ege_physics'])
    
    class Meta:
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'
        ordering = ['last_name', 'first_name']


class Homework(models.Model):
    """Домашнее задание"""
    
    SUBJECT_CHOICES = [
        ('math', 'Математика'),
        ('physics', 'Физика'),
    ]
    
    STATUS_CHOICES = [
        ('assigned', 'Назначено'),
        ('in_progress', 'В работе'),
        ('checked', 'Проверено'),
    ]
    
    GRADE_CHOICES = [
        ('5', 'Отлично (5)'),
        ('4', 'Хорошо (4)'),
        ('3', 'Удовлетворительно (3)'),
        ('2', 'Неудовлетворительно (2)'),
        ('z', 'Зачтено'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='homework')
    assigned_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, 
                                   related_name='assigned_homework', verbose_name='Назначил')
    
    title = models.CharField(max_length=200, verbose_name='Название задания')
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, verbose_name='Предмет')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned', verbose_name='Статус')
    
    assigned_date = models.DateField(verbose_name='Дата выдачи', auto_now_add=True)
    deadline = models.DateField(null=True, blank=True, verbose_name='Дедлайн сдачи')
    submitted_date = models.DateField(null=True, blank=True, verbose_name='Дата отправки')
    checked_date = models.DateField(null=True, blank=True, verbose_name='Дата проверки')
    
    teacher_comment = models.TextField(verbose_name='Комментарий преподавателя', blank=True)
    grade = models.CharField(
        max_length=5, 
        null=True, 
        blank=True, 
        verbose_name='Оценка', 
        choices=GRADE_CHOICES
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.student}"
    
    def is_overdue(self):
        """Проверить, просрочено ли задание"""
        if self.deadline and self.status != 'checked':
            return timezone.now().date() > self.deadline
        return False
    
    def get_deadline_status(self):
        """Получить статус дедлайна"""
        if self.status == 'checked':
            return 'checked'
        if not self.deadline:
            return 'not_set'
        today = timezone.now().date()
        days_left = (self.deadline - today).days
        if days_left < 0:
            return 'overdue'
        elif days_left <= 3:
            return 'urgent'
        elif days_left <= 7:
            return 'soon'
        else:
            return 'normal'
    
    def has_student_files(self):
        """Проверить, есть ли файлы ученика"""
        return self.files.filter(file_type='student').exists()
    
    def get_student_files_count(self):
        """Получить количество файлов ученика"""
        return self.files.filter(file_type='student').count()
    
    def get_teacher_files_count(self):
        """Получить количество файлов преподавателя"""
        return self.files.filter(file_type='teacher').count()
    
    def get_all_files(self):
        """Получить все файлы"""
        return self.files.all()
    
    def get_status_display_with_color(self):
        """Получить статус с цветом для отображения"""
        status_colors = {
            'assigned': 'secondary',
            'in_progress': 'info',
            'checked': 'success',
        }
        return {
            'status': self.get_status_display(),
            'color': status_colors.get(self.status, 'secondary')
        }
    
    def get_grade_display_formatted(self):
        """Получить отформатированное отображение оценки"""
        grade_dict = dict(self.GRADE_CHOICES)
        return grade_dict.get(self.grade, '—')
    
    class Meta:
        verbose_name = 'Домашнее задание'
        verbose_name_plural = 'Домашние задания'
        ordering = ['-assigned_date']


class HomeworkFile(models.Model):
    """Файлы для домашнего задания"""
    
    FILE_TYPE_CHOICES = [
        ('teacher', 'Файл преподавателя'),
        ('student', 'Файл ученика'),
    ]
    
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='homework_files/%Y/%m/%d/', verbose_name='Файл')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='teacher', 
                                verbose_name='Тип файла')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name='Загрузил')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200, verbose_name='Описание файла', blank=True)
    
    def __str__(self):
        return f"{self.description or 'Файл'} - {self.homework.title}"
    
    class Meta:
        verbose_name = 'Файл домашнего задания'
        verbose_name_plural = 'Файлы домашних заданий'


class Probnik(models.Model):
    """Модель пробника"""
    
    SUBJECT_CHOICES = [
        ('math', 'Математика'),
        ('physics', 'Физика'),
    ]
    
    STATUS_CHOICES = [
        ('in_progress', 'В работе'),
        ('checked', 'Проверен'),
    ]
    
    MONTH_CHOICES = [
        ('', '---------'),
        ('september', 'Сентябрь'),
        ('october', 'Октябрь'),
        ('november', 'Ноябрь'),
        ('december', 'Декабрь'),
        ('january', 'Январь'),
        ('february', 'Февраль'),
        ('march', 'Март'),
        ('april', 'Апрель'),
        ('may', 'Май'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='probniks')
    assigned_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, 
                                   related_name='assigned_probniks', verbose_name='Назначил')
    
    title = models.CharField(max_length=200, verbose_name='Название пробника')
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, verbose_name='Предмет')
    
    month = models.CharField(
        max_length=20, 
        choices=MONTH_CHOICES, 
        blank=True, 
        null=True,
        verbose_name='Месяц аттестации', 
        help_text='Выберите месяц для ежемесячной аттестации'
    )
    
    assigned_date = models.DateField(verbose_name='Дата назначения', auto_now_add=True)
    deadline = models.DateField(null=True, blank=True, verbose_name='Дедлайн сдачи')
    completed_date = models.DateField(null=True, blank=True, verbose_name='Дата выполнения')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', verbose_name='Статус')
    
    score = models.IntegerField(null=True, blank=True, verbose_name='Баллы')
    max_score = models.IntegerField(default=100, verbose_name='Максимальный балл')
    grade = models.CharField(
        max_length=5, 
        null=True, 
        blank=True, 
        verbose_name='Оценка', 
        choices=[
            ('5', 'Отлично (5)'), 
            ('4', 'Хорошо (4)'), 
            ('3', 'Удовлетворительно (3)'), 
            ('2', 'Неудовлетворительно (2)')
        ]
    )
    teacher_comment = models.TextField(verbose_name='Комментарий преподавателя', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.student}"
    
    def is_overdue(self):
        """Проверить, просрочен ли пробник"""
        if self.deadline and self.status == 'in_progress':
            return timezone.now().date() > self.deadline
        return False
    
    def get_deadline_status(self):
        """Получить статус дедлайна"""
        if not self.deadline or self.status == 'checked':
            return 'completed'
        today = timezone.now().date()
        days_left = (self.deadline - today).days
        if days_left < 0:
            return 'overdue'
        elif days_left <= 3:
            return 'urgent'
        elif days_left <= 7:
            return 'soon'
        else:
            return 'normal'
    
    def get_percentage(self):
        """Рассчитать процент выполнения"""
        if self.score is not None and self.max_score > 0:
            return round((self.score / self.max_score) * 100, 1)
        return None
    
    def get_grade_from_score(self):
        """Получить оценку на основе баллов"""
        if self.score is None or self.max_score is None or self.max_score <= 0:
            return None
        
        percentage = (self.score / self.max_score) * 100
        
        if percentage >= 85:
            return '5'
        elif percentage >= 70:
            return '4'
        elif percentage >= 50:
            return '3'
        else:
            return '2'
    
    def has_student_files(self):
        """Проверить, есть ли файлы ученика"""
        return self.files.filter(file_type='student').exists()
    
    def get_student_files_count(self):
        """Получить количество файлов ученика"""
        return self.files.filter(file_type='student').count()
    
    def get_teacher_files_count(self):
        """Получить количество файлов преподавателя"""
        return self.files.filter(file_type='teacher').count()
    
    def get_all_files(self):
        """Получить все файлы"""
        return self.files.all()
    
    class Meta:
        verbose_name = 'Пробник'
        verbose_name_plural = 'Пробники'
        ordering = ['-assigned_date']


class ProbnikFile(models.Model):
    """Файлы для пробника"""
    
    FILE_TYPE_CHOICES = [
        ('teacher', 'Файл преподавателя'),
        ('student', 'Файл ученика'),
    ]
    
    probnik = models.ForeignKey(Probnik, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='probnik_files/%Y/%m/%d/', verbose_name='Файл')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='teacher', 
                                verbose_name='Тип файла')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name='Загрузил')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200, verbose_name='Описание файла', blank=True)
    
    def __str__(self):
        return f"{self.description or 'Файл'} - {self.probnik.title}"
    
    class Meta:
        verbose_name = 'Файл пробника'
        verbose_name_plural = 'Файлы пробников'


class StudyFile(models.Model):
    """Модель учебных файлов"""
    
    SUBJECT_CHOICES = [
        ('math', 'Математика'),
        ('physics', 'Физика'),
        ('general', 'Общие материалы'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('theory', 'Теория'),
        ('practice', 'Практика'),
        ('demo', 'Демоверсия'),
        ('template', 'Шаблон'),
        ('other', 'Другое'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='study_files')
    uploaded_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, 
                                   related_name='uploaded_files', verbose_name='Загрузил')
    title = models.CharField(max_length=200, verbose_name='Название файла')
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, 
                              default='general', verbose_name='Предмет')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='theory',
                                verbose_name='Тип файла')
    file = models.FileField(upload_to='study_files/%Y/%m/%d/', verbose_name='Файл')
    description = models.TextField(verbose_name='Описание файла', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_subject_display()}: {self.title}"
    
    class Meta:
        verbose_name = 'Учебный файл'
        verbose_name_plural = 'Учебные файлы'
        ordering = ['-uploaded_at']


# ================ СИГНАЛЫ ДЛЯ УДАЛЕНИЯ ФАЙЛОВ ================

@receiver(post_delete, sender=HomeworkFile)
def delete_homework_file_from_storage(sender, instance, **kwargs):
    """
    Удаляет файл из файловой системы при удалении записи HomeworkFile
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            print(f"Файл {instance.file.path} удален из файловой системы")


@receiver(post_delete, sender=ProbnikFile)
def delete_probnik_file_from_storage(sender, instance, **kwargs):
    """
    Удаляет файл из файловой системы при удалении записи ProbnikFile
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            print(f"Файл {instance.file.path} удален из файловой системы")


@receiver(post_delete, sender=StudyFile)
def delete_study_file_from_storage(sender, instance, **kwargs):
    """
    Удаляет файл из файловой системы при удалении записи StudyFile
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
            print(f"Файл {instance.file.path} удален из файловой системы")


@receiver(pre_delete, sender=Homework)
def delete_homework_all_files(sender, instance, **kwargs):
    """
    Удаляет все связанные файлы при удалении Homework
    """
    files = HomeworkFile.objects.filter(homework=instance)
    for file in files:
        if file.file and os.path.isfile(file.file.path):
            os.remove(file.file.path)
            print(f"Файл {file.file.path} удален при удалении домашнего задания")


@receiver(pre_delete, sender=Probnik)
def delete_probnik_all_files(sender, instance, **kwargs):
    """
    Удаляет все связанные файлы при удалении Probnik
    """
    files = ProbnikFile.objects.filter(probnik=instance)
    for file in files:
        if file.file and os.path.isfile(file.file.path):
            os.remove(file.file.path)
            print(f"Файл {file.file.path} удален при удалении пробника")