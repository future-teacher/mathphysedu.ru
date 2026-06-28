from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from .models import Teacher, Student, Homework, Probnik, ProbnikFile, StudyFile, HomeworkFile
from .forms import StudentForm, HomeworkForm, ProbnikForm, StudyFileForm, TeacherProfileForm
from .telegram_bot import (
    notify_student_new_homework,
    notify_student_homework_checked,
    notify_student_new_probnik,
    notify_student_probnik_checked,
    notify_teacher_homework_submitted,
)
import random
import string


def is_teacher(user):
    """Проверка, является ли пользователь преподавателем или администратором"""
    return user.is_authenticated and (
        hasattr(user, 'teacher_profile') or 
        user.is_staff or 
        user.is_superuser
    )


def get_teacher_or_admin(user):
    """
    Возвращает профиль преподавателя для пользователя.
    Если пользователь - администратор без профиля, создает его.
    В противном случае возвращает None.
    """
    try:
        return user.teacher_profile
    except Teacher.DoesNotExist:
        if user.is_staff or user.is_superuser:
            teacher, created = Teacher.objects.get_or_create(
                user=user,
                defaults={'bio': 'Администратор системы'}
            )
            return teacher
        return None


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_dashboard(request):
    """Дашборд преподавателя"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    total_students = teacher.students.count()
    today = timezone.now().date()
    
    active_homework = Homework.objects.filter(
        assigned_by=teacher
    ).filter(
        Q(deadline__gte=today) | Q(deadline__isnull=True)
    ).count()
    
    overdue_homework = Homework.objects.filter(
        assigned_by=teacher,
        deadline__lt=today
    ).count()
    
    active_probniks = Probnik.objects.filter(
        assigned_by=teacher,
        status='in_progress'
    ).count()
    
    checked_probniks = Probnik.objects.filter(
        assigned_by=teacher,
        status='checked'
    ).count()
    
    students = teacher.students.all().order_by('last_name', 'first_name')[:10]
    
    search_query = request.GET.get('search', '')
    if search_query:
        students = teacher.students.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(class_name__icontains=search_query)
        ).order_by('last_name', 'first_name')[:10]
    
    recent_homework = Homework.objects.filter(
        assigned_by=teacher
    ).order_by('-created_at')[:5]
    
    recent_probniks = Probnik.objects.filter(
        assigned_by=teacher
    ).order_by('-created_at')[:5]
    
    recent_files = StudyFile.objects.filter(
        uploaded_by=teacher
    ).order_by('-uploaded_at')[:5]
    
    context = {
        'teacher': teacher,
        'total_students': total_students,
        'active_homework': active_homework,
        'overdue_homework': overdue_homework,
        'active_probniks': active_probniks,
        'to_check_probniks': checked_probniks,
        'students': students,
        'search_query': search_query,
        'recent_homework': recent_homework,
        'recent_probniks': recent_probniks,
        'recent_files': recent_files,
    }
    
    return render(request, 'students/teacher_dashboard.html', context)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def student_list(request):
    """Список учеников преподавателя"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        students = Student.objects.all().order_by('last_name', 'first_name')
    else:
        students = teacher.students.all().order_by('last_name', 'first_name')
    
    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(class_name__icontains=search_query) |
            Q(telegram_username__icontains=search_query) |
            Q(parent_telegram__icontains=search_query)
        )
    
    return render(request, 'students/teacher_student_list.html', {
        'teacher': teacher,
        'students': students,
        'search_query': search_query,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def student_create(request):
    """Создание нового ученика"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.method == 'POST':
        form = StudentForm(request.POST, teacher=teacher)
        if form.is_valid():
            student = form.save(commit=False)
            student.teacher = teacher
            
            if form.cleaned_data.get('create_user', True):
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')
                
                if not username:
                    username = f"{student.first_name.lower()}_{student.last_name.lower()}"
                    counter = 1
                    original_username = username
                    while User.objects.filter(username=username).exists():
                        username = f"{original_username}_{counter}"
                        counter += 1
                
                if not password:
                    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=student.first_name,
                    last_name=student.last_name
                )
                student.user = user
                
                request.session['new_student_credentials'] = {
                    'username': username,
                    'password': password,
                    'student_name': f"{student.first_name} {student.last_name}"
                }
            
            student.save()
            messages.success(request, f'Ученик {student} успешно создан!')
            
            credentials = request.session.get('new_student_credentials')
            if credentials:
                messages.info(request, 
                    f'Данные для входа ученика:<br>'
                    f'Логин: <strong>{credentials["username"]}</strong><br>'
                    f'Пароль: <strong>{credentials["password"]}</strong>'
                )
                del request.session['new_student_credentials']
            
            return redirect('teacher_student_list')
    else:
        form = StudentForm(teacher=teacher)
    
    return render(request, 'students/teacher_student_form.html', {
        'teacher': teacher,
        'form': form,
        'title': 'Добавить ученика',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def student_detail(request, student_id):
    """Детальная информация об ученике"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        student = get_object_or_404(Student, id=student_id)
    else:
        student = get_object_or_404(Student, id=student_id, teacher=teacher)
    
    # Все ДЗ по математике (не только активные)
    math_homework = student.homework.filter(subject='math').order_by('-assigned_date')[:20]
    
    # Все ДЗ по физике (не только активные)
    physics_homework = student.homework.filter(subject='physics').order_by('-assigned_date')[:20]
    
    # Пробники
    math_probniks = student.probniks.filter(subject='math').order_by('-assigned_date')[:20]
    physics_probniks = student.probniks.filter(subject='physics').order_by('-assigned_date')[:20]
    
    # Учебные файлы
    all_study_files = student.study_files.all().order_by('-uploaded_at')
    math_files = all_study_files.filter(subject='math')[:10]
    physics_files = all_study_files.filter(subject='physics')[:10]
    general_files = all_study_files.filter(subject='general')[:10]
    
    context = {
        'teacher': teacher,
        'student': student,
        'math_homework': math_homework,
        'physics_homework': physics_homework,
        'math_probniks': math_probniks,
        'physics_probniks': physics_probniks,
        'math_files': math_files,
        'physics_files': physics_files,
        'general_files': general_files,
        'all_study_files': all_study_files,
    }
    
    return render(request, 'students/teacher_student_detail.html', context)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def student_edit(request, student_id):
    """Редактирование ученика"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        student = get_object_or_404(Student, id=student_id)
    else:
        student = get_object_or_404(Student, id=student_id, teacher=teacher)
    
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student, teacher=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные ученика {student} обновлены!')
            return redirect('teacher_student_detail', student_id=student.id)
    else:
        form = StudentForm(instance=student, teacher=teacher)
    
    return render(request, 'students/teacher_student_form.html', {
        'teacher': teacher,
        'form': form,
        'student': student,
        'title': 'Редактировать ученика',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def homework_create(request):
    """Создание домашнего задания"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.method == 'POST':
        form = HomeworkForm(request.POST)
        if form.is_valid():
            homework = form.save(commit=False)
            homework.assigned_by = teacher
            
            if not homework.deadline:
                homework.deadline = timezone.now().date() + timezone.timedelta(days=7)
            
            homework.save()
            
            files = request.FILES.getlist('files')
            for uploaded_file in files:
                HomeworkFile.objects.create(
                    homework=homework,
                    file=uploaded_file,
                    file_type='teacher',
                    uploaded_by=request.user,
                    description=f"Материал к заданию '{homework.title}'"
                )
            
            # Отправляем уведомление ученику о новом ДЗ
            notify_student_new_homework(homework)
            
            # Проверяем, указан ли Telegram у ученика
            student = homework.student
            if not student.telegram_username:
                messages.warning(
                    request,
                    f'У ученика {student.first_name} {student.last_name} не указан Telegram. '
                    f'Уведомление не будет отправлено.'
                )
            
            messages.success(request, f'Задание "{homework.title}" создано!')
            return redirect('teacher_dashboard')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = HomeworkForm()
        if hasattr(request.user, 'teacher_profile'):
            form.fields['student'].queryset = request.user.teacher_profile.students.all()
        else:
            form.fields['student'].queryset = Student.objects.all()
    
    return render(request, 'students/teacher_homework_form.html', {
        'teacher': teacher,
        'form': form,
        'title': 'Добавить домашнее задание',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def homework_list(request):
    """Список домашних заданий"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        homework_list = Homework.objects.all().order_by('-assigned_date')
    else:
        homework_list = Homework.objects.filter(assigned_by=teacher).order_by('-assigned_date')
    
    subject_filter = request.GET.get('subject', 'all')
    if subject_filter != 'all':
        homework_list = homework_list.filter(subject=subject_filter)
    
    status_filter = request.GET.get('status', 'all')
    today = timezone.now().date()
    
    if status_filter == 'active':
        # Активные - не проверенные и не просроченные
        homework_list = homework_list.exclude(status='checked').filter(
            Q(deadline__gte=today) | Q(deadline__isnull=True)
        ).distinct()
    elif status_filter == 'checked':
        # Проверенные
        homework_list = homework_list.filter(status='checked')
    elif status_filter == 'overdue':
        # Просроченные (не проверенные и дедлайн прошел)
        homework_list = homework_list.filter(
            deadline__lt=today
        ).exclude(status='checked')
    
    paginator = Paginator(homework_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'students/teacher_homework_list.html', {
        'teacher': teacher,
        'homework_list': page_obj,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'today': today,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def homework_detail(request, homework_id):
    """Детальная информация о домашнем задании"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        homework = get_object_or_404(Homework, id=homework_id)
    else:
        homework = get_object_or_404(Homework, id=homework_id, assigned_by=teacher)
    
    teacher_files = homework.files.filter(file_type='teacher')
    student_files = homework.files.filter(file_type='student')
    today = timezone.now().date()
    
    if request.method == 'POST':
        if 'add_file' in request.POST:
            files = request.FILES.getlist('files')
            for uploaded_file in files:
                HomeworkFile.objects.create(
                    homework=homework,
                    file=uploaded_file,
                    file_type='teacher',
                    uploaded_by=request.user,
                    description=f"Дополнительный материал от {timezone.now().strftime('%d.%m.%Y')}"
                )
            messages.success(request, 'Файл добавлен!')
            return redirect('teacher_homework_detail', homework_id=homework.id)
        
        elif 'check_homework' in request.POST:
            grade = request.POST.get('grade')
            teacher_comment = request.POST.get('teacher_comment')
            
            if not grade:
                messages.error(request, 'Пожалуйста, выберите оценку')
                return redirect('teacher_homework_detail', homework_id=homework.id)
            
            homework.status = 'checked'
            homework.checked_date = timezone.now().date()
            homework.grade = grade
            homework.teacher_comment = teacher_comment
            homework.save()
            
            # Отправляем уведомление ученику о проверке ДЗ
            notify_student_homework_checked(homework)
            
            grade_display = dict(homework._meta.get_field('grade').choices).get(homework.grade, '—')
            messages.success(request, f'✅ Домашнее задание проверено! Оценка: {grade_display}')
            
            return redirect('teacher_homework_detail', homework_id=homework.id)
    
    return render(request, 'students/teacher_homework_detail.html', {
        'teacher': teacher,
        'homework': homework,
        'teacher_files': teacher_files,
        'student_files': student_files,
        'today': today,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_probnik_create(request):
    """Создание пробника преподавателем"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.method == 'POST':
        form = ProbnikForm(request.POST)
        if form.is_valid():
            probnik = form.save(commit=False)
            probnik.assigned_by = teacher
            probnik.save()
            
            files = request.FILES.getlist('files')
            for uploaded_file in files:
                ProbnikFile.objects.create(
                    probnik=probnik,
                    file=uploaded_file,
                    file_type='teacher',
                    uploaded_by=request.user,
                    description=f"Материалы пробника"
                )
            
            # Отправляем уведомление ученику о новом пробнике
            notify_student_new_probnik(probnik)
            
            # Проверяем, указан ли Telegram у ученика
            student = probnik.student
            if not student.telegram_username:
                messages.warning(
                    request,
                    f'У ученика {student.first_name} {student.last_name} не указан Telegram. '
                    f'Уведомление не будет отправлено.'
                )
            
            messages.success(request, f'Пробник "{probnik.title}" успешно создан!')
            return redirect('teacher_probnik_list')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProbnikForm()
        if hasattr(request.user, 'teacher_profile'):
            form.fields['student'].queryset = request.user.teacher_profile.students.all()
        else:
            form.fields['student'].queryset = Student.objects.all()
    
    return render(request, 'students/teacher_probnik_form.html', {
        'teacher': teacher,
        'form': form,
        'title': 'Создать пробник',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_probnik_list(request):
    """Список всех пробников преподавателя"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        probniks = Probnik.objects.all().order_by('-assigned_date')
    else:
        probniks = Probnik.objects.filter(assigned_by=teacher).order_by('-assigned_date')
    
    subject_filter = request.GET.get('subject', 'all')
    if subject_filter != 'all':
        probniks = probniks.filter(subject=subject_filter)
    
    status_filter = request.GET.get('status', 'all')
    today = timezone.now().date()
    if status_filter == 'active':
        probniks = probniks.filter(status='in_progress')
    elif status_filter == 'checked':
        probniks = probniks.filter(status='checked')
    elif status_filter == 'overdue':
        probniks = probniks.filter(
            status='in_progress',
            deadline__lt=today
        )
    
    paginator = Paginator(probniks, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'students/teacher_probnik_list.html', {
        'teacher': teacher,
        'probniks': page_obj,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'today': today,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_probnik_detail(request, probnik_id):
    """Детальная страница пробника для преподавателя"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        probnik = get_object_or_404(Probnik, id=probnik_id)
    else:
        probnik = get_object_or_404(Probnik, id=probnik_id, assigned_by=teacher)
    
    teacher_files = probnik.files.filter(file_type='teacher')
    student_files = probnik.files.filter(file_type='student')
    today = timezone.now().date()
    
    if request.method == 'POST':
        if 'check_probnik' in request.POST:
            score = request.POST.get('score')
            grade = request.POST.get('grade')
            teacher_comment = request.POST.get('teacher_comment')
            
            if score:
                probnik.score = int(score) if score else None
            
            if grade:
                probnik.grade = grade
            elif probnik.score:
                probnik.grade = probnik.get_grade_from_score()
            
            probnik.teacher_comment = teacher_comment
            probnik.status = 'checked'
            probnik.save()
            
            # Отправляем уведомление ученику о проверке пробника
            notify_student_probnik_checked(probnik)
            
            grade_display = dict(probnik._meta.get_field('grade').choices).get(probnik.grade, '—')
            messages.success(
                request,
                f'✅ Пробник проверен! Оценка: {grade_display}, Баллы: {probnik.score}/{probnik.max_score}'
            )
            
            return redirect('teacher_probnik_detail', probnik_id=probnik.id)
        
        elif 'add_file' in request.POST:
            files = request.FILES.getlist('files')
            if files:
                for uploaded_file in files:
                    ProbnikFile.objects.create(
                        probnik=probnik,
                        file=uploaded_file,
                        file_type='teacher',
                        uploaded_by=request.user,
                        description=f"Дополнительные материалы: {uploaded_file.name}"
                    )
                messages.success(request, f'Добавлено файлов: {len(files)}')
            else:
                messages.warning(request, 'Выберите файлы для загрузки')
            return redirect('teacher_probnik_detail', probnik_id=probnik.id)
    
    context = {
        'teacher': teacher,
        'probnik': probnik,
        'teacher_files': teacher_files,
        'student_files': student_files,
        'today': today,
        'has_solutions': student_files.exists(),
    }
    
    return render(request, 'students/teacher_probnik_detail.html', context)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_probnik_edit(request, probnik_id):
    """Редактирование пробника"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        probnik = get_object_or_404(Probnik, id=probnik_id)
    else:
        probnik = get_object_or_404(Probnik, id=probnik_id, assigned_by=teacher)
    
    if request.method == 'POST':
        form = ProbnikForm(request.POST, instance=probnik)
        if form.is_valid():
            form.save()
            messages.success(request, f'Пробник "{probnik.title}" обновлен!')
            return redirect('teacher_probnik_detail', probnik_id=probnik.id)
    else:
        form = ProbnikForm(instance=probnik)
        if hasattr(request.user, 'teacher_profile'):
            form.fields['student'].queryset = request.user.teacher_profile.students.all()
    
    return render(request, 'students/teacher_probnik_form.html', {
        'teacher': teacher,
        'form': form,
        'probnik': probnik,
        'title': 'Редактировать пробник',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_probnik_delete(request, probnik_id):
    """Удаление пробника преподавателем"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        probnik = get_object_or_404(Probnik, id=probnik_id)
    else:
        probnik = get_object_or_404(Probnik, id=probnik_id, assigned_by=teacher)
    
    if request.method == 'POST':
        probnik_title = probnik.title
        student_name = str(probnik.student)
        probnik.delete()  # Сигнал pre_delete удалит все связанные файлы
        messages.success(request, f'Пробник "{probnik_title}" для ученика {student_name} и все связанные файлы успешно удалены!')
        return redirect('teacher_probnik_list')
    
    return render(request, 'students/teacher_probnik_confirm_delete.html', {
        'teacher': teacher,
        'probnik': probnik,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def study_file_create(request):
    """Загрузка учебного файла"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.method == 'POST':
        form = StudyFileForm(request.POST, request.FILES)
        if form.is_valid():
            study_file = form.save(commit=False)
            study_file.uploaded_by = teacher
            study_file.save()
            messages.success(request, f'Файл "{study_file.title}" загружен!')
            return redirect('teacher_student_detail', student_id=study_file.student.id)
    else:
        form = StudyFileForm()
        if hasattr(request.user, 'teacher_profile'):
            form.fields['student'].queryset = request.user.teacher_profile.students.all()
        else:
            form.fields['student'].queryset = Student.objects.all()
    
    return render(request, 'students/teacher_studyfile_form.html', {
        'teacher': teacher,
        'form': form,
        'title': 'Загрузить учебный файл',
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def homework_delete(request, homework_id):
    """Удаление домашнего задания"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.user.is_staff or request.user.is_superuser:
        homework = get_object_or_404(Homework, id=homework_id)
    else:
        homework = get_object_or_404(Homework, id=homework_id, assigned_by=teacher)
    
    if request.method == 'POST':
        homework_title = homework.title
        homework.delete()  # Сигнал pre_delete удалит все связанные файлы
        messages.success(request, f'Задание "{homework_title}" и все связанные файлы удалены!')
        return redirect('teacher_homework_list')
    
    return render(request, 'students/teacher_homework_delete.html', {
        'teacher': teacher,
        'homework': homework,
    })


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def delete_teacher_homework_file(request, file_id):
    """Удаление файла преподавателя из домашнего задания"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    file = get_object_or_404(HomeworkFile, id=file_id)
    homework_id = file.homework.id
    
    if not (teacher == file.homework.assigned_by or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав на удаление этого файла')
        return redirect('teacher_homework_detail', homework_id=homework_id)
    
    if request.method == 'POST':
        file.delete()  # Сигнал post_delete удалит файл из файловой системы
        messages.success(request, 'Файл успешно удален из базы данных и файловой системы')
    
    return redirect('teacher_homework_detail', homework_id=homework_id)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def delete_teacher_probnik_file(request, file_id):
    """Удаление файла пробника"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    file = get_object_or_404(ProbnikFile, id=file_id)
    probnik_id = file.probnik.id
    
    if not (teacher == file.probnik.assigned_by or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав на удаление этого файла')
        return redirect('teacher_probnik_detail', probnik_id=probnik_id)
    
    if request.method == 'POST':
        file.delete()  # Сигнал post_delete удалит файл из файловой системы
        messages.success(request, 'Файл удален из базы данных и файловой системы')
    
    return redirect('teacher_probnik_detail', probnik_id=probnik_id)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def delete_study_file(request, file_id):
    """Удаление учебного файла"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    file = get_object_or_404(StudyFile, id=file_id)
    student_id = file.student.id
    
    if not (teacher == file.uploaded_by or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'У вас нет прав на удаление этого файла')
        return redirect('teacher_student_detail', student_id=student_id)
    
    if request.method == 'POST':
        file.delete()  # Сигнал post_delete удалит файл из файловой системы
        messages.success(request, f'Файл "{file.title}" успешно удален из базы данных и файловой системы')
    
    return redirect('teacher_student_detail', student_id=student_id)


@login_required
@user_passes_test(is_teacher, login_url='/students/login/')
def teacher_profile_edit(request):
    """Редактирование профиля преподавателя"""
    teacher = get_teacher_or_admin(request.user)
    if not teacher:
        messages.error(request, 'У вас нет прав преподавателя')
        return redirect('login')
    
    if request.method == 'POST':
        form = TeacherProfileForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Профиль успешно обновлён!')
            return redirect('teacher_dashboard')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = TeacherProfileForm(instance=teacher)
    
    return render(request, 'students/teacher_profile_form.html', {
        'teacher': teacher,
        'form': form,
        'title': 'Мой профиль',
    })