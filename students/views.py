from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from .models import Student, Probnik, ProbnikFile, StudyFile, Homework, HomeworkFile
from django.core.paginator import Paginator


def landing(request):
    """Главная страница с внешней информацией"""
    return render(request, 'students/landing.html')

def student_login(request):
    """Вход для учеников"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Проверяем, является ли пользователь учеником
                if hasattr(user, 'student_profile') and user.student_profile:
                    return redirect('dashboard')
                # Проверяем, является ли пользователь преподавателем или админом
                if hasattr(user, 'teacher_profile') and user.teacher_profile:
                    return redirect('teacher_dashboard')
                # Если пользователь - staff/superuser без профиля, создаём профиль преподавателя
                if user.is_staff or user.is_superuser:
                    from .models import Teacher
                    teacher, created = Teacher.objects.get_or_create(
                        user=user,
                        defaults={'bio': 'Администратор системы'}
                    )
                    return redirect('teacher_dashboard')
                messages.error(request, 'У вас нет доступа к системе')
                return redirect('login')
    else:
        form = AuthenticationForm()
    return render(request, 'students/login.html', {'form': form})


@login_required
def dashboard(request):
    """Личный кабинет ученика"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к личному кабинету ученика')
        return redirect('login')
    
    today = timezone.now().date()
    
    all_homework = student.homework.all().order_by('-assigned_date')
    
    # Получаем последние проверенные работы (для верхнего блока)
    recent_checked_homework = student.homework.filter(
        status='checked'
    ).order_by('-checked_date')[:5]
    
    # Активные задания (не проверенные и с дедлайном в будущем или без дедлайна)
    active_homework = all_homework.filter(
        Q(deadline__gte=today) | Q(deadline__isnull=True)
    ).exclude(status='checked')
    active_homework = active_homework.distinct()
    
    # Активные задания по предметам
    math_homework = active_homework.filter(subject='math')[:5]
    physics_homework = active_homework.filter(subject='physics')[:5]
    
    # Проверенные задания по предметам (последние 5)
    math_checked_homework = student.homework.filter(
        subject='math',
        status='checked'
    ).order_by('-checked_date')[:5]
    
    physics_checked_homework = student.homework.filter(
        subject='physics',
        status='checked'
    ).order_by('-checked_date')[:5]
    
    # Просроченные задания
    overdue_homework = all_homework.filter(
        deadline__lt=today
    ).exclude(status='checked')
    math_overdue = overdue_homework.filter(subject='math')[:3]
    physics_overdue = overdue_homework.filter(subject='physics')[:3]
    
    week_ago = today - timezone.timedelta(days=7)
    new_homework = student.homework.filter(
        assigned_date__gte=week_ago
    ).order_by('-assigned_date')
    
    math_active_probniks = student.probniks.filter(
        subject='math',
        status='in_progress'
    ).order_by('deadline')
    
    math_completed_probniks = student.probniks.filter(
        subject='math',
        status='checked'
    ).order_by('-assigned_date')[:5]
    
    physics_active_probniks = student.probniks.filter(
        subject='physics',
        status='in_progress'
    ).order_by('deadline')
    
    physics_completed_probniks = student.probniks.filter(
        subject='physics',
        status='checked'
    ).order_by('-assigned_date')[:5]
    
    study_files = student.study_files.all()
    math_files = study_files.filter(subject='math').order_by('-uploaded_at')
    physics_files = study_files.filter(subject='physics').order_by('-uploaded_at')
    general_files = study_files.filter(subject='general').order_by('-uploaded_at')
    
    active_exams = []
    for exam_name, exam_date in student.get_active_exam_dates():
        if exam_date and exam_date >= today:
            days_left = (exam_date - today).days
            active_exams.append({
                'name': exam_name,
                'date': exam_date,
                'days_left': days_left,
                'is_near': days_left <= 30
            })
    
    active_exams.sort(key=lambda x: x['date'])
    
    return render(request, 'students/dashboard.html', {
        'student': student,
        'recent_checked_homework': recent_checked_homework,
        'active_homework': active_homework,
        'math_homework': math_homework,
        'physics_homework': physics_homework,
        'math_checked_homework': math_checked_homework,
        'physics_checked_homework': physics_checked_homework,
        'math_overdue': math_overdue,
        'physics_overdue': physics_overdue,
        'new_homework': new_homework,
        'math_active_probniks': math_active_probniks,
        'math_completed_probniks': math_completed_probniks,
        'physics_active_probniks': physics_active_probniks,
        'physics_completed_probniks': physics_completed_probniks,
        'math_files': math_files,
        'physics_files': physics_files,
        'general_files': general_files,
        'active_exams': active_exams,
        'today': today,
        'week_ago': week_ago,
    })


@login_required
def homework_list(request):
    """Список домашних заданий ученика"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к домашним заданиям')
        return redirect('login')
    
    subject_filter = request.GET.get('subject', 'all')
    status_filter = request.GET.get('status', 'all')
    
    homework = student.homework.all()
    
    if subject_filter != 'all':
        homework = homework.filter(subject=subject_filter)
    
    # Фильтр по статусу
    if status_filter == 'assigned':
        homework = homework.filter(status='assigned')
    elif status_filter == 'in_progress':
        homework = homework.filter(status='in_progress')
    elif status_filter == 'submitted':
        homework = homework.filter(status='submitted')
    elif status_filter == 'checked':
        homework = homework.filter(status='checked')
    elif status_filter == 'overdue':
        today = timezone.now().date()
        homework = homework.filter(
            status__in=['assigned', 'in_progress', 'submitted'],
            deadline__lt=today
        )
    
    homework = homework.order_by('-assigned_date')
    
    # Пагинация
    paginator = Paginator(homework, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Статистика
    total_homework = student.homework.count()
    assigned_count = student.homework.filter(status='assigned').count()
    in_progress_count = student.homework.filter(status='in_progress').count()
    submitted_count = student.homework.filter(status='submitted').count()
    checked_count = student.homework.filter(status='checked').count()
    
    today = timezone.now().date()
    overdue_count = student.homework.filter(
        status__in=['assigned', 'in_progress', 'submitted'],
        deadline__lt=today
    ).count()
    
    math_count = student.homework.filter(subject='math').count()
    physics_count = student.homework.filter(subject='physics').count()
    
    return render(request, 'students/homework_list.html', {
        'student': student,
        'homework': page_obj,
        'subject_filter': subject_filter,
        'status_filter': status_filter,
        'total_homework': total_homework,
        'assigned_count': assigned_count,
        'in_progress_count': in_progress_count,
        'submitted_count': submitted_count,
        'checked_count': checked_count,
        'overdue_count': overdue_count,
        'math_count': math_count,
        'physics_count': physics_count,
        'today': today,
    })


@login_required
def homework_detail(request, homework_id):
    """Детальная страница домашнего задания"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к домашним заданиям')
        return redirect('login')
    
    homework = get_object_or_404(Homework, id=homework_id, student=student)
    
    teacher_files = homework.files.filter(file_type='teacher')
    student_files = homework.files.filter(file_type='student')
    today = timezone.now().date()
    
    if request.method == 'POST':
        if 'student_files' in request.FILES:
            files = request.FILES.getlist('student_files')
            for uploaded_file in files:
                HomeworkFile.objects.create(
                    homework=homework,
                    file=uploaded_file,
                    file_type='student',
                    uploaded_by=request.user,
                    description=f"Файл ученика от {timezone.now().strftime('%d.%m.%Y')}"
                )
            
            if homework.status == 'assigned':
                homework.status = 'in_progress'
                homework.save()
            
            messages.success(request, 'Файлы успешно загружены!')
            return redirect('homework_detail', homework_id=homework.id)
        
        elif 'submit_homework' in request.POST:
            if homework.files.filter(file_type='student').exists():
                homework.status = 'submitted'
                homework.submitted_date = today
                homework.save()
                messages.success(request, '✅ Домашнее задание отправлено на проверку!')
            else:
                messages.warning(request, 'Сначала загрузите файлы с решением.')
            return redirect('homework_detail', homework_id=homework.id)
    
    return render(request, 'students/homework_detail.html', {
        'student': student,
        'homework': homework,
        'teacher_files': teacher_files,
        'student_files': student_files,
        'today': today,
    })


@login_required
def probnik_list(request):
    """Список пробников ученика"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к пробникам')
        return redirect('login')
    
    subject_filter = request.GET.get('subject', 'all')
    status_filter = request.GET.get('status', 'all')
    month_filter = request.GET.get('month', 'all')
    
    probniks = student.probniks.all()
    
    if subject_filter != 'all':
        probniks = probniks.filter(subject=subject_filter)
    
    if status_filter == 'active':
        probniks = probniks.filter(status='in_progress')
    elif status_filter == 'completed':
        probniks = probniks.filter(status='checked')
    elif status_filter == 'overdue':
        probniks = probniks.filter(
            status='in_progress',
            deadline__lt=timezone.now().date()
        )
    
    if month_filter != 'all' and month_filter:
        probniks = probniks.filter(month=month_filter)
    
    probniks = probniks.order_by('-assigned_date')
    
    total_probniks = student.probniks.count()
    active_count = student.probniks.filter(status='in_progress').count()
    completed_count = student.probniks.filter(status='checked').count()
    overdue_count = student.probniks.filter(
        status='in_progress',
        deadline__lt=timezone.now().date()
    ).count()
    
    math_count = student.probniks.filter(subject='math').count()
    physics_count = student.probniks.filter(subject='physics').count()
    
    return render(request, 'students/probnik_list.html', {
        'student': student,
        'probniks': probniks,
        'subject_filter': subject_filter,
        'status_filter': status_filter,
        'month_filter': month_filter,
        'total_probniks': total_probniks,
        'active_count': active_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'math_count': math_count,
        'physics_count': physics_count,
        'today': timezone.now().date(),
    })


@login_required
def probnik_detail(request, probnik_id):
    """Детальная страница пробника"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к пробникам')
        return redirect('login')
    
    probnik = get_object_or_404(Probnik, id=probnik_id, student=student)
    
    teacher_files = probnik.files.filter(file_type='teacher')
    student_files = probnik.files.filter(file_type='student')
    today = timezone.now().date()
    
    if request.method == 'POST':
        if 'student_files' in request.FILES:
            files = request.FILES.getlist('student_files')
            for uploaded_file in files:
                ProbnikFile.objects.create(
                    probnik=probnik,
                    file=uploaded_file,
                    file_type='student',
                    uploaded_by=request.user,
                    description=f"Решение от {timezone.now().strftime('%d.%m.%Y %H:%M')}"
                )
            
            messages.success(request, 'Файлы успешно загружены!')
            return redirect('probnik_detail', probnik_id=probnik.id)
        
        elif 'submit_probnik' in request.POST:
            if not probnik.files.filter(file_type='student').exists():
                messages.warning(request, 'Пожалуйста, загрузите файлы с решением перед отправкой.')
                return redirect('probnik_detail', probnik_id=probnik.id)
            
            probnik.status = 'checked'
            probnik.completed_date = today
            probnik.save()
            
            messages.success(request, 
                '✅ Пробник отправлен на проверку! Преподаватель получил уведомление и скоро проверит работу.'
            )
            
            return redirect('probnik_detail', probnik_id=probnik.id)
    
    return render(request, 'students/probnik_detail.html', {
        'student': student,
        'probnik': probnik,
        'teacher_files': teacher_files,
        'student_files': student_files,
        'today': today,
    })


@login_required
def delete_probnik(request, probnik_id):
    """Удаление пробника учеником"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к этому действию')
        return redirect('login')
    
    probnik = get_object_or_404(Probnik, id=probnik_id, student=student)
    
    if probnik.status != 'in_progress':
        messages.error(request, 'Нельзя удалить пробник, который уже проверен')
        return redirect('probnik_detail', probnik_id=probnik.id)
    
    if request.method == 'POST':
        probnik_title = probnik.title
        probnik.delete()  # Сигнал pre_delete удалит все связанные файлы
        messages.success(request, f'Пробник "{probnik_title}" и все связанные файлы успешно удалены!')
        return redirect('probnik_list')
    
    return render(request, 'students/probnik_confirm_delete.html', {
        'student': student,
        'probnik': probnik,
    })


@login_required
def student_detail(request):
    """Страница профиля ученика"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к профилю ученика')
        return redirect('login')
    
    exam_date = None
    exam_name = None
    
    active_exams = student.get_active_exam_dates()
    if active_exams:
        exam_name, exam_date = active_exams[0]
    
    return render(request, 'students/student_detail.html', {
        'student': student,
        'exam_date': exam_date,
        'exam_name': exam_name,
    })


@login_required
def delete_homework_file(request, file_id):
    """Удаление файла ученика из домашнего задания"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к этому действию')
        return redirect('login')
    
    file = get_object_or_404(HomeworkFile, id=file_id, uploaded_by=request.user, file_type='student')
    homework_id = file.homework.id
    
    if request.method == 'POST':
        file.delete()  # Сигнал post_delete удалит файл из файловой системы
        
        # Проверяем, остались ли еще файлы ученика
        homework = file.homework
        if not homework.files.filter(file_type='student').exists():
            if homework.status == 'in_progress' or homework.status == 'submitted':
                homework.status = 'assigned'
                homework.save()
        
        messages.success(request, 'Файл успешно удален из базы данных и файловой системы')
    
    return redirect('homework_detail', homework_id=homework_id)


@login_required
def delete_probnik_file(request, file_id):
    """Удаление файла ученика из пробника"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к этому действию')
        return redirect('login')
    
    file = get_object_or_404(ProbnikFile, id=file_id, uploaded_by=request.user, file_type='student')
    probnik_id = file.probnik.id
    
    if file.probnik.status != 'in_progress':
        messages.error(request, 'Нельзя удалить файлы после отправки на проверку')
        return redirect('probnik_detail', probnik_id=probnik_id)
    
    if request.method == 'POST':
        file.delete()  # Сигнал post_delete удалит файл из файловой системы
        messages.success(request, 'Файл успешно удален из базы данных и файловой системы')
    
    return redirect('probnik_detail', probnik_id=probnik_id)