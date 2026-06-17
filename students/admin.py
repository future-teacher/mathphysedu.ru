from django.contrib import admin
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Student, Probnik, ProbnikFile, StudyFile, Homework, HomeworkFile, Teacher


# --- Базовый класс для инлайнов с файлами ---
class BaseFileInline(admin.TabularInline):
    extra = 1
    fields = ('file', 'file_type', 'description', 'uploaded_by')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["initial"] = request.user
            kwargs["queryset"] = request.user.__class__.objects.filter(id=request.user.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.uploaded_by_id:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()


class HomeworkFileInline(BaseFileInline):
    model = HomeworkFile


class ProbnikFileInline(BaseFileInline):
    model = ProbnikFile


class StudyFileInline(admin.TabularInline):
    model = StudyFile
    extra = 1
    fields = ('title', 'subject', 'file_type', 'file', 'description')


class StudentAdminForm(forms.ModelForm):
    """Форма для ученика"""
    
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
    
    class Meta:
        model = Student
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            selected_types = self.instance.get_exam_types_list()
            self.fields['exam_type_choices'].initial = selected_types
    
    def save(self, commit=True):
        selected_types = self.cleaned_data.get('exam_type_choices', [])
        self.instance.exam_types = ','.join(selected_types)
        return super().save(commit=commit)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'telegram', 'phone', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'telegram', 'phone')
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Имя'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('first_name', 'last_name', 'class_name', 'telegram_username', 
                    'display_exam_types', 'current_level', 'start_date')
    list_filter = ('class_name', 'current_level', 'start_date')
    search_fields = ('first_name', 'last_name', 'telegram_username', 'parent_telegram')
    inlines = [StudyFileInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'teacher', 'first_name', 'last_name', 'class_name')
        }),
        ('Контактная информация (Telegram)', {
            'fields': ('telegram_username', 'parent_name', 'parent_telegram'),
            'description': 'Введите Telegram username (например: @username)'
        }),
        ('Учебная информация', {
            'fields': ('school', 'exam_type_choices', 'current_level', 
                      'weak_topics', 'start_date')
        }),
        ('Даты экзаменов (заполняйте только выбранные)', {
            'fields': ('exam_date_oge_math', 'exam_date_oge_physics',
                      'exam_date_ege_math', 'exam_date_ege_physics'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def display_exam_types(self, obj):
        exam_types = obj.get_exam_types_display()
        return ', '.join(exam_types) if exam_types else '-'
    display_exam_types.short_description = 'Типы подготовки'


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'subject', 'assigned_date', 'deadline', 'get_status_display')
    list_filter = ('subject', 'assigned_date', 'deadline')
    search_fields = ('title', 'student__first_name', 'student__last_name')
    readonly_fields = ('assigned_date',)
    inlines = [HomeworkFileInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('student', 'assigned_by', 'title', 'subject')
        }),
        ('Даты', {
            'fields': ('assigned_date', 'deadline')
        }),
    )
    
    def get_status_display(self, obj):
        if obj.is_overdue():
            return 'Просрочено'
        elif obj.deadline:
            days_left = (obj.deadline - timezone.now().date()).days
            return f'Активно (осталось {days_left} дн.)'
        else:
            return 'Активно'
    get_status_display.short_description = 'Статус'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.assigned_date = timezone.now().date()
        super().save_model(request, obj, form, change)


@admin.register(HomeworkFile)
class HomeworkFileAdminSeparate(admin.ModelAdmin):
    list_display = ('homework', 'description', 'file_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_by')
    search_fields = ('homework__title', 'description', 'uploaded_by__username')
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["initial"] = request.user
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Probnik)
class ProbnikAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'subject', 'status', 'deadline', 'score', 'max_score', 'get_percentage_display')
    list_filter = ('subject', 'status', 'assigned_date', 'deadline')
    search_fields = ('title', 'student__first_name', 'student__last_name')
    readonly_fields = ('assigned_date', 'created_at', 'updated_at')
    inlines = [ProbnikFileInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('student', 'assigned_by', 'title', 'subject')
        }),
        ('Статус и даты', {
            'fields': ('status', 'assigned_date', 'deadline', 'completed_date')
        }),
        ('Результаты', {
            'fields': ('score', 'max_score', 'teacher_comment'),
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_percentage_display(self, obj):
        percentage = obj.get_percentage()
        if percentage:
            return f"{percentage}%"
        return "-"
    get_percentage_display.short_description = 'Процент'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.assigned_date = timezone.now().date()
        super().save_model(request, obj, form, change)


@admin.register(ProbnikFile)
class ProbnikFileAdmin(admin.ModelAdmin):
    list_display = ('probnik', 'description', 'file_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_by')
    search_fields = ('probnik__title', 'description', 'uploaded_by__username')
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "uploaded_by":
            kwargs["initial"] = request.user
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StudyFile)
class StudyFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'subject', 'file_type', 'uploaded_at')
    list_filter = ('subject', 'file_type', 'student')
    search_fields = ('title', 'description', 'student__first_name', 'student__last_name')