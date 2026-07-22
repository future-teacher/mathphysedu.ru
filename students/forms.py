from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Student, Homework, Probnik, ProbnikFile, StudyFile, HomeworkFile, Teacher


class TeacherRegistrationForm(forms.ModelForm):
    """Форма регистрации преподавателя"""
    username = forms.CharField(max_length=150, label='Имя пользователя')
    password = forms.CharField(widget=forms.PasswordInput, label='Пароль')
    email = forms.EmailField(required=False, label='Email')
    first_name = forms.CharField(max_length=30, label='Имя')
    last_name = forms.CharField(max_length=30, label='Фамилия')
    
    class Meta:
        model = Teacher
        fields = ['phone', 'telegram', 'bio']
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError('Пользователь с таким именем уже существует')
        return username
    
    def save(self, commit=True):
        user_data = self.cleaned_data
        user = User.objects.create_user(
            username=user_data['username'],
            password=user_data['password'],
            email=user_data.get('email', ''),
            first_name=user_data['first_name'],
            last_name=user_data['last_name']
        )
        
        teacher = super().save(commit=False)
        teacher.user = user
        if commit:
            teacher.save()
        return teacher


class StudentForm(forms.ModelForm):
    """Форма для создания/редактирования ученика"""
    
    EXAM_TYPE_CHOICES = [
        ('oge_math', 'ОГЭ по математике'),
        ('oge_physics', 'ОГЭ по физике'),
        ('ege_math', 'ЕГЭ по математике'),
        ('ege_physics', 'ЕГЭ по физике'),
        ('improvement', 'Повышение успеваемости'),
    ]
    
    exam_type_choices = forms.MultipleChoiceField(
        choices=EXAM_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Типы подготовки'
    )
    
    exam_date_oge_math = forms.DateField(
        required=False,
        label='Дата ОГЭ по математике',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    exam_date_oge_physics = forms.DateField(
        required=False,
        label='Дата ОГЭ по физике',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    exam_date_ege_math = forms.DateField(
        required=False,
        label='Дата ЕГЭ по математике',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    exam_date_ege_physics = forms.DateField(
        required=False,
        label='Дата ЕГЭ по физике',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    create_user = forms.BooleanField(
        initial=True,
        required=False,
        label='Создать пользователя для ученика'
    )
    
    username = forms.CharField(
        required=False,
        label='Логин для ученика',
        help_text='Если не указан, будет сгенерирован автоматически',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}, render_value=True),
        label='Пароль для ученика',
        help_text='Если не указан, будет сгенерирован автоматически'
    )
    
    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'class_name', 'telegram_username',
                 'parent_name', 'parent_telegram', 'school', 'current_level',
                 'weak_topics', 'start_date', 'google_sheet_url', 'notes']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'class_name': forms.TextInput(attrs={'class': 'form-control'}),
            'telegram_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
            'parent_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_telegram': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
            'school': forms.TextInput(attrs={'class': 'form-control'}),
            'current_level': forms.TextInput(attrs={'class': 'form-control'}),
            'weak_topics': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'google_sheet_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://docs.google.com/spreadsheets/d/...'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            self.fields['create_user'].initial = False
            self.fields['create_user'].disabled = True
            self.fields['username'].disabled = True
            self.fields['password'].disabled = True
            
            if self.instance.exam_types:
                selected_types = [t.strip() for t in self.instance.exam_types.split(',') if t.strip()]
                self.fields['exam_type_choices'].initial = selected_types
            
            self.fields['exam_date_oge_math'].initial = self.instance.exam_date_oge_math
            self.fields['exam_date_oge_physics'].initial = self.instance.exam_date_oge_physics
            self.fields['exam_date_ege_math'].initial = self.instance.exam_date_ege_math
            self.fields['exam_date_ege_physics'].initial = self.instance.exam_date_ege_physics
    
    def save(self, commit=True):
        selected_types = self.cleaned_data.get('exam_type_choices', [])
        self.instance.exam_types = ','.join(selected_types)
        
        self.instance.exam_date_oge_math = self.cleaned_data.get('exam_date_oge_math')
        self.instance.exam_date_oge_physics = self.cleaned_data.get('exam_date_oge_physics')
        self.instance.exam_date_ege_math = self.cleaned_data.get('exam_date_ege_math')
        self.instance.exam_date_ege_physics = self.cleaned_data.get('exam_date_ege_physics')
        
        if self.teacher:
            self.instance.teacher = self.teacher
            
        return super().save(commit=commit)


class HomeworkForm(forms.ModelForm):
    """Форма для создания домашнего задания"""
    
    class Meta:
        model = Homework
        fields = ['student', 'title', 'subject', 'deadline', 'status']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название задания'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = 'assigned'
        self.fields['status'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        
        if student and subject:
            if subject == 'math' and not student.has_math:
                raise ValidationError(
                    f'Ученик {student.first_name} {student.last_name} не занимается математикой. '
                    f'Выберите другого ученика или измените предмет.'
                )
            elif subject == 'physics' and not student.has_physics:
                raise ValidationError(
                    f'Ученик {student.first_name} {student.last_name} не занимается физикой. '
                    f'Выберите другого ученика или измените предмет.'
                )
        
        return cleaned_data


class HomeworkCheckForm(forms.ModelForm):
    """Форма для проверки домашнего задания"""
    
    class Meta:
        model = Homework
        fields = ['status', 'grade', 'teacher_comment']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'grade': forms.Select(attrs={'class': 'form-control'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Комментарий к работе'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [('checked', 'Проверено')]
        self.fields['status'].initial = 'checked'
        self.fields['status'].widget.attrs['disabled'] = True
        self.fields['grade'].label = 'Результат'
        self.fields['teacher_comment'].label = 'Комментарий'
        self.fields['teacher_comment'].help_text = 'Напишите комментарий к работе'


class HomeworkFileForm(forms.ModelForm):
    """Форма для загрузки файлов к домашнему заданию"""
    
    class Meta:
        model = HomeworkFile
        fields = ['file', 'description', 'file_type']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Описание файла'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
        }


class ProbnikForm(forms.ModelForm):
    """Форма для создания/редактирования пробника"""
    
    class Meta:
        model = Probnik
        fields = ['student', 'title', 'subject', 'month', 'deadline', 'max_score', 'status', 'score', 'teacher_comment', 'is_hidden']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название пробника'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'month': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'value': 100}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Комментарий к работе'}),
            'is_hidden': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['max_score'].required = False
        
        if not self.instance.pk:
            self.fields['deadline'].initial = timezone.now().date() + timezone.timedelta(days=7)
            self.fields['score'].required = False
            self.fields['teacher_comment'].required = False
            self.fields['status'].initial = 'in_progress'
    
    def clean_max_score(self):
        max_score = self.cleaned_data.get('max_score')
        if max_score is None:
            return 100
        return max_score
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        
        if student and subject:
            if subject == 'math' and not student.has_math:
                raise ValidationError(
                    f'Ученик {student.first_name} {student.last_name} не занимается математикой. '
                    f'Выберите другого ученика или измените предмет.'
                )
            elif subject == 'physics' and not student.has_physics:
                raise ValidationError(
                    f'Ученик {student.first_name} {student.last_name} не занимается физикой. '
                    f'Выберите другого ученика или измените предмет.'
                )
        
        return cleaned_data


class ProbnikCheckForm(forms.ModelForm):
    """Форма для проверки пробника"""
    
    class Meta:
        model = Probnik
        fields = ['score', 'teacher_comment']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Комментарий к работе'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['score'].label = 'Баллы'
        self.fields['teacher_comment'].label = 'Комментарий'
        self.fields['score'].help_text = 'Введите количество набранных баллов'
        self.fields['teacher_comment'].help_text = 'Напишите разбор ошибок и рекомендации'


class StudyFileForm(forms.ModelForm):
    """Форма для загрузки учебных файлов"""
    
    class Meta:
        model = StudyFile
        fields = ['student', 'title', 'subject', 'file_type', 'file', 'description']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название файла'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'file_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Описание файла'}),
        }


class TeacherProfileForm(forms.ModelForm):
    """Форма редактирования профиля преподавателя"""

    first_name = forms.CharField(
        max_length=30, label='Имя',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, label='Фамилия',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False, label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Teacher
        fields = ['phone', 'telegram', 'bio']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
            'telegram': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'О себе...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        teacher = super().save(commit=commit)
        user = teacher.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
        return teacher