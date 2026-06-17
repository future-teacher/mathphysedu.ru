from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import teacher_views

urlpatterns = [
    # Главная страница
    path('', views.landing, name='landing'),
    
    # Аутентификация
    path('login/', views.student_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/students/login/'), name='logout'),
    
    # Ученики
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.student_detail, name='student_detail'),
    
    # Домашние задания для учеников
    path('homework/', views.homework_list, name='homework_list'),
    path('homework/<int:homework_id>/', views.homework_detail, name='homework_detail'),
    path('homework/file/<int:file_id>/delete/', views.delete_homework_file, name='delete_homework_file'),
    
    # Пробники для учеников
    path('probniks/', views.probnik_list, name='probnik_list'),
    path('probnik/<int:probnik_id>/', views.probnik_detail, name='probnik_detail'),
    path('probnik/<int:probnik_id>/delete/', views.delete_probnik, name='delete_probnik'),
    path('probnik/file/<int:file_id>/delete/', views.delete_probnik_file, name='delete_probnik_file'),
    
    # Преподаватели - основное
    path('teacher/dashboard/', teacher_views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/students/', teacher_views.student_list, name='teacher_student_list'),
    path('teacher/students/create/', teacher_views.student_create, name='teacher_student_create'),
    path('teacher/students/<int:student_id>/', teacher_views.student_detail, name='teacher_student_detail'),
    path('teacher/students/<int:student_id>/edit/', teacher_views.student_edit, name='teacher_student_edit'),
    
    # Преподаватели - домашние задания
    path('teacher/homework/', teacher_views.homework_list, name='teacher_homework_list'),
    path('teacher/homework/create/', teacher_views.homework_create, name='teacher_homework_create'),
    path('teacher/homework/<int:homework_id>/', teacher_views.homework_detail, name='teacher_homework_detail'),
    path('teacher/homework/<int:homework_id>/delete/', teacher_views.homework_delete, name='teacher_homework_delete'),
    path('teacher/homework/file/<int:file_id>/delete/', teacher_views.delete_teacher_homework_file, 
         name='teacher_delete_homework_file'),
    
    # Преподаватели - пробники
    path('teacher/probniks/', teacher_views.teacher_probnik_list, name='teacher_probnik_list'),
    path('teacher/probnik/create/', teacher_views.teacher_probnik_create, name='teacher_probnik_create'),
    path('teacher/probnik/<int:probnik_id>/', teacher_views.teacher_probnik_detail, name='teacher_probnik_detail'),
    path('teacher/probnik/<int:probnik_id>/edit/', teacher_views.teacher_probnik_edit, name='teacher_probnik_edit'),
    path('teacher/probnik/<int:probnik_id>/delete/', teacher_views.teacher_probnik_delete, name='teacher_probnik_delete'),
    path('teacher/probnik/file/<int:file_id>/delete/', teacher_views.delete_teacher_probnik_file, 
         name='teacher_delete_probnik_file'),
    
    # Преподаватели - учебные файлы
    path('teacher/files/create/', teacher_views.study_file_create, name='teacher_studyfile_create'),
    path('teacher/studyfile/<int:file_id>/delete/', teacher_views.delete_study_file, 
         name='teacher_delete_study_file'),
]