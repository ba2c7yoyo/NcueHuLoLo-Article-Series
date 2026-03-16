from django.contrib import admin
from .models import Course, CourseAlias, UserInfo
from import_export.admin import ImportExportModelAdmin

@admin.register(CourseAlias)
class CourseAliasAdmin(ImportExportModelAdmin):
    list_display = ('course_name', 'alias')
    
@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin):
    list_display = ('teacher_name','course_name')
    
@admin.register(UserInfo)
class UserInfoAdmin(ImportExportModelAdmin):
    list_display = ('display_name', 'year', 'join_date')
    search_fields = ('display_name', 'user_id', 'year')