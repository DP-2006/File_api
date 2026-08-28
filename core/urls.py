      

from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views
from .views import get_all_roles_detailed

# Import از views_management
from .views_management import (
    create_role_advanced_api,
    get_role_password_policy_api,
    update_role_password_policy_api,
    assign_role_to_users_bulk_api,
    assign_multiple_roles_to_user_api,
    get_user_roles_with_permissions_api,
    remove_role_from_user_api,
    get_users_by_role_api,
    bulk_block_users_api,
    bulk_change_password_api,
    update_role_api,  # <--- این خط را اضافه کنید
)

urlpatterns = [
    
    # ========== Auth ==========
    path('', views.login_view, name='login'),
    path('login/', csrf_exempt(views.login_view), name='login_view'),
    path('logout/', views.logout_view, name='logout'),
    path('logout-token/', views.log_out_view, name='logout_token'),
    
    # ========== Dashboard ==========
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_files_view, name='upload_files'),
    path('save-settings/', views.save_settings_view, name='save_settings'),
    path('download/<int:file_id>/', views.download_file_view, name='download_file'),
    path('delete-my-file/', views.delete_my_file_view, name='delete_my_file'),
    path('debug-files/', views.debug_files_view, name='debug_files'),
    
    # ========== Admin ==========
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    path('super-admin-panel/', views.super_admin_panel, name='super_admin_panel'),
    path('admin-action/', views.admin_action_view, name='admin_action'),
    path('api/admin-action/', views.admin_action_view, name='admin_action_api'),
    path('super-admin-action/', views.super_admin_action, name='super_admin_action'),
    
    # ========== Users ==========
    path('api/users/', views.api_users, name='api_users'),
    path('users/list/', views.get_users_list, name='get_users_list'),
    path('users/<int:user_id>/', views.user_detail_view, name='user_detail'),
    path('users/<int:user_id>/toggle-block/', views.toggle_block_user, name='toggle_block_user'),
    path('users/<int:user_id>/delete/', views.delete_user_by_id, name='delete_user_by_id'),
    path('users/me/permissions/', views.my_permissions_view, name='my_permissions'),
    path('users/analyze/<int:user_id>/', views.analyze_user_view, name='analyze_user'),
    path('users/personality/<int:user_id>/', views.analyze_user_personality_view, name='analyze_personality'),
    
    # API جدید برای کاربران (با api/ prefix)
    path('api/users-list/', views.get_users_list_api, name='get_users_list_api'),
    path('api/toggle-block/<int:user_id>/', views.toggle_block_user, name='toggle_block_user_api'),
    path('api/delete-user/<int:user_id>/', views.delete_user_by_id, name='delete_user_by_id_api'),
    
    # ========== Roles & Permissions ==========
    path('roles/', views.get_all_roles, name='get_all_roles'),
    path('roles/create/', views.create_new_role, name='create_new_role'),
    path('roles/<int:role_id>/delete/', views.delete_role_view, name='delete_role'),
    path('roles/<int:role_id>/permissions/', views.get_role_permissions, name='get_role_permissions'),
    path('roles/save-permissions/', views.save_role_permissions, name='save_role_permissions'),
    path('permissions/', views.get_all_permissions, name='get_all_permissions'),
    path('create-role/', views.create_role_view, name='create_role'),
    
    # API جدید برای نقش‌ها (با api/ prefix)
    path('api/roles/', views.get_all_roles_api, name='get_all_roles_api'),
    path('api/all-permissions/', views.get_all_permissions_api, name='get_all_permissions_api'),
    path('api/role-permissions/<int:role_id>/', views.get_role_permissions_api, name='get_role_permissions_api'),
    path('api/save-role-permissions/', views.save_role_permissions_api, name='save_role_permissions_api'),
    path('api/create-role/', views.create_role_api, name='create_role_api'),
    path('api/delete-role/<int:role_id>/', views.delete_role_api, name='delete_role_api'),
    
    # ========== Files ==========
    path('send-files/', views.send_files_view, name='send_files'),
    path('file-summary/<int:file_id>/', views.file_summary_view, name='file_summary'),
    path('analyze-file/<int:file_id>/', views.analyze_file_with_ai, name='analyze_file'),
    path('analyze-file-manual/<int:file_id>/', views.analyze_file_manual_api, name='analyze_file_manual'),
    path('analyze-all-files/', views.analyze_all_files_view, name='analyze_all_files'),
    path('analyze-all-users/', views.analyze_all_users_view, name='analyze_all_users'),
    path('file-analysis/<int:file_id>/', views.analyze_file_detail_view, name='file_analysis_detail'),
    
    # ========== Alerts & Security ==========
    path('security-alerts/', views.security_alerts_view, name='security_alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert_view, name='resolve_alert'),
    path('alerts/count/', views.alerts_count_view, name='alerts_count'),
    path('alerts/stats/', views.security_stats_view, name='security_stats'),
    path('alerts/count-api/', views.alerts_count_api, name='alerts_count_api'),
    path('notifications/', views.notifications_html_view, name='notifications'),
    path('api/notifications/', views.get_notifications_api, name='get_notifications'),
    path('api/notifications/<int:notification_id>/read/', views.mark_notification_read_api, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read_api, name='mark_all_notifications_read'),
    
    # ========== Logs ==========
    path('login-logs/', views.login_logs_view, name='login_logs'),
    path('action-logs/', views.action_log_view, name='action_logs'),
    path('action-logs/<int:log_id>/', views.action_log_detail_api, name='action_log_detail'),
    
    # API جدید برای لاگ‌ها (با api/ prefix)
    path('api/logs/', views.get_logs_api, name='get_logs_api'),
    path('api/logs/clear/', views.clear_logs_api, name='clear_logs_api'),
    
    # ========== AI Settings ==========
    path('ai-settings/', views.ai_settings_panel, name='ai_settings'),
    path('ai-test-connection/', views.ai_test_connection_api, name='ai_test_connection'),
    path('ai-save-settings/', views.ai_save_settings_api, name='ai_save_settings'),
    path('ai-get-models/', views.ai_get_models_api, name='ai_get_models'),
    path('ai-restart-ollama/', views.ai_restart_ollama_api, name='ai_restart_ollama'),
    
    # ========== Network Settings ==========
    path('network-info/', views.get_network_info_api, name='network_info'),
    path('network-save/', views.save_network_settings_api, name='network_save'),
    path('network-apply/', views.apply_network_settings_api, name='network_apply'),
    
    # ========== Password Policy ==========
    path('password-policy/', views.set_password_policy, name='password_policy'),
    
    # ========== Bulk Operations ==========
    path('bulk-delete-users/', views.bulk_delete_users_view, name='bulk_delete_users'),
    path('bulk-delete-roles/', views.bulk_delete_roles_view, name='bulk_delete_roles'),

    # ========== Delete Modals ==========
    path('delete-user-modal/<int:user_id>/', views.delete_user_modal_view, name='delete_user_modal'),
    path('delete-role-modal/<int:role_id>/', views.delete_role_modal_view, name='delete_role_modal'),
    path('delete-user/<int:user_id>/', views.delete_user_view, name='delete_user'),
    path('api/roles/detailed/', get_all_roles_detailed, name='api_roles_detailed'),

    # ========== File Size Settings ==========
    path('api/file-size-settings/', views.get_file_size_settings_api, name='get_file_size_settings'),
    path('api/file-size-settings/save/', views.save_file_size_settings_api, name='save_file_size_settings'),

    # ========== Role Management Advanced ==========
    path('api/roles/create-advanced/', create_role_advanced_api, name='create_role_advanced'),
    path('api/roles/<int:role_id>/password-policy/', get_role_password_policy_api, name='get_role_password_policy'),
    path('api/roles/<int:role_id>/password-policy/update/', update_role_password_policy_api, name='update_role_password_policy'),
    path('api/roles/<int:role_id>/users/', get_users_by_role_api, name='get_users_by_role'),
    path('api/roles/<int:role_id>/update/', update_role_api, name='update_role_api'),  # <--- استفاده از update_role_api که import شده
    
    # ========== Bulk Role Assignment ==========
    path('api/roles/assign-bulk/', assign_role_to_users_bulk_api, name='assign_role_bulk'),
    path('api/users/assign-multiple-roles/', assign_multiple_roles_to_user_api, name='assign_multiple_roles'),
    path('api/users/<int:user_id>/roles/', get_user_roles_with_permissions_api, name='get_user_roles'),
    path('api/users/remove-role/', remove_role_from_user_api, name='remove_role_from_user'),
    
    # ========== Bulk User Management ==========
    path('api/users/bulk-block/', bulk_block_users_api, name='bulk_block_users'),
    path('api/users/bulk-change-password/', bulk_change_password_api, name='bulk_change_password'),
]