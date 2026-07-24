import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseNotAllowed
from .models import Student, Probnik, ProbnikFile, StudyFile, Homework, HomeworkFile, Application
from .telegram_bot import (
    notify_teacher_homework_submitted,
    notify_teacher_probnik_submitted,
    process_single_update,
)
from django.core.paginator import Paginator


def landing(request):
    """Главная страница с внешней информацией"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        exam_type = request.POST.get('exam_type', '').strip()
        
        if name and phone and exam_type:
            Application.objects.create(
                name=name,
                phone=phone,
                exam_type=exam_type
            )
            messages.success(request, '✅ Спасибо! Ваша заявка принята. Я свяжусь с вами в ближайшее время.')
        else:
            messages.error(request, 'Пожалуйста, заполните все поля формы.')
        
        return redirect('landing')
    
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
        status='in_progress',
        is_hidden=False
    ).order_by('deadline')
    
    math_completed_probniks = student.probniks.filter(
        subject='math',
        status='checked',
        is_hidden=False
    ).order_by('-assigned_date')[:5]
    
    physics_active_probniks = student.probniks.filter(
        subject='physics',
        status='in_progress',
        is_hidden=False
    ).order_by('deadline')
    
    physics_completed_probniks = student.probniks.filter(
        subject='physics',
        status='checked',
        is_hidden=False
    ).order_by('-assigned_date')[:5]
    
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
    
    # === ДОСТИЖЕНИЯ (ГЕЙМИФИКАЦИЯ) ===
    math_total = student.homework.filter(subject='math').count()
    physics_total = student.homework.filter(subject='physics').count()
    total_all = student.homework.count()
    completed_all = student.homework.filter(status='checked').count()
    
    achievements = []
    if math_total >= 10:
        achievements.append('🧮 Математический боец')
    if physics_total >= 10:
        achievements.append('⚡ Физический гений')
    if completed_all >= 5:
        achievements.append('🏆 Первые шаги')
    if total_all >= 20:
        achievements.append('🎯 Трудоголик')
    if not any(student.probniks.filter(status='in_progress')):
        achievements.append('📚 Все пробники сданы!')
    
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
        'active_exams': active_exams,
        'today': today,
        'week_ago': week_ago,
        'achievements': achievements,
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
    
    # Домашние задания в работе (assigned, in_progress)
    in_progress_homework = student.homework.filter(
        status__in=['assigned', 'in_progress']
    )
    # Проверенные домашние задания
    checked_homework = student.homework.filter(status='checked')
    
    if subject_filter != 'all':
        in_progress_homework = in_progress_homework.filter(subject=subject_filter)
        checked_homework = checked_homework.filter(subject=subject_filter)
    
    in_progress_homework = in_progress_homework.order_by('-assigned_date')
    checked_homework = checked_homework.order_by('-checked_date')
    
    today = timezone.now().date()
    
    math_count = student.homework.filter(subject='math').count()
    physics_count = student.homework.filter(subject='physics').count()
    
    return render(request, 'students/homework_list.html', {
        'student': student,
        'in_progress_homework': in_progress_homework,
        'checked_homework': checked_homework,
        'subject_filter': subject_filter,
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
            
            # Отправляем уведомление преподавателю о загруженных файлах
            notify_teacher_homework_submitted(homework)
            
            messages.success(request, '🎉 Отлично! Файлы успешно загружены! Преподаватель получил уведомление.')
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
    
    # Активные пробники (в работе)
    active_probniks = student.probniks.filter(status='in_progress', is_hidden=False)
    # Проверенные пробники
    completed_probniks = student.probniks.filter(status='checked', is_hidden=False)
    
    if subject_filter != 'all':
        active_probniks = active_probniks.filter(subject=subject_filter)
        completed_probniks = completed_probniks.filter(subject=subject_filter)
    
    active_probniks = active_probniks.order_by('deadline')
    completed_probniks = completed_probniks.order_by('-assigned_date')
    
    math_count = student.probniks.filter(subject='math', is_hidden=False).count()
    physics_count = student.probniks.filter(subject='physics', is_hidden=False).count()
    
    return render(request, 'students/probnik_list.html', {
        'student': student,
        'active_probniks': active_probniks,
        'completed_probniks': completed_probniks,
        'subject_filter': subject_filter,
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
    
    probnik = get_object_or_404(Probnik, id=probnik_id, student=student, is_hidden=False)
    
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
            
            # Отправляем уведомление преподавателю о загруженных файлах
            notify_teacher_probnik_submitted(probnik)
            
            messages.success(request, '🎉 Файлы успешно загружены! Преподаватель получил уведомление.')
            return redirect('probnik_detail', probnik_id=probnik.id)
        
        elif 'submit_probnik' in request.POST:
            if not probnik.files.filter(file_type='student').exists():
                messages.warning(request, 'Пожалуйста, загрузите файлы с решением перед отправкой.')
                return redirect('probnik_detail', probnik_id=probnik.id)
            
            probnik.status = 'checked'
            probnik.completed_date = today
            probnik.save()
            
            # Отправляем уведомление преподавателю
            notify_teacher_probnik_submitted(probnik)
            
            messages.success(request,
                '🚀 Отлично! Пробник отправлен на проверку! Преподаватель получил уведомление и скоро проверит работу.'
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
def study_materials(request):
    """Страница учебных материалов ученика"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'У вас нет доступа к учебным материалам')
        return redirect('login')
    
    study_files = student.study_files.all()
    math_files = study_files.filter(subject='math').order_by('-uploaded_at')
    physics_files = study_files.filter(subject='physics').order_by('-uploaded_at')
    general_files = study_files.filter(subject='general').order_by('-uploaded_at')
    
    return render(request, 'students/study_materials.html', {
        'student': student,
        'math_files': math_files,
        'physics_files': physics_files,
        'general_files': general_files,
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
            if homework.status == 'in_progress':
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


@csrf_exempt
def telegram_webhook(request):
    """
    Webhook endpoint для Telegram Bot API.
    
    Telegram отправляет POST-запрос с JSON-данными сюда,
    когда пользователь пишет боту. Это позволяет отвечать
    на /start мгновенно, без polling.
    
    URL: /students/telegram/webhook/
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    try:
        update_data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponse('Invalid JSON', status=400)
    
    process_single_update(update_data)
    
    # Telegram ожидает ответ 200 OK
    return HttpResponse('ok')