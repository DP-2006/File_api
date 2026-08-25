# serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
from .models import (
    FileActionLog, UploadedFile, UserSettings, UserProfile,
    PasswordPolicy, GroupLeader, LoginLog, AINotification, 
    AIThreatAlert, SystemPermission, UserPermission, AISettings, 
    SystemSettings
)


# =============================================
# ============ User Serializers ============
# =============================================

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'is_active', 'is_staff', 'is_superuser', 
            'date_joined', 'last_login', 'role', 'groups'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_role(self, obj):
        if obj.is_superuser:
            return 'superadmin'
        elif obj.is_staff:
            return 'admin'
        else:
            return 'user'

    def get_groups(self, obj):
        return [{'id': g.id, 'name': g.name} for g in obj.groups.all()]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'confirm_password',
            'first_name', 'last_name', 'is_staff', 'is_active'
        ]

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "رمز عبور و تکرار آن مطابقت ندارند"})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'user_id', 'is_blocked', 'blocked_at',
            'phone', 'address', 'bio', 'profile_picture', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# =============================================
# ============ File Serializers ============
# =============================================

class UploadedFileSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    is_document = serializers.SerializerMethodField()
    sent_to_user_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UploadedFile
        fields = [
            'id', 'file', 'file_url', 'file_size', 'file_extension',
            'uploaded_at', 'uploaded_by', 'folder_name', 'is_deleted',
            'save_to_cloud', 'sent_to_user', 'sent_to_user_info',
            'is_image', 'is_document'
        ]
        read_only_fields = ['id', 'uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_size(self, obj):
        if obj.file:
            try:
                return obj.file.size
            except:
                return 0
        return 0

    def get_file_extension(self, obj):
        if obj.file:
            name = obj.file.name
            return name.split('.')[-1].lower() if '.' in name else 'unknown'
        return None

    def get_is_image(self, obj):
        ext = self.get_file_extension(obj)
        return ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']

    def get_is_document(self, obj):
        ext = self.get_file_extension(obj)
        return ext in ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx']

    def get_sent_to_user_info(self, obj):
        if obj.sent_to_user:
            return {
                'id': obj.sent_to_user.id,
                'username': obj.sent_to_user.username,
                'full_name': f"{obj.sent_to_user.first_name} {obj.sent_to_user.last_name}".strip()
            }
        return None


class UploadedFileDetailSerializer(UploadedFileSerializer):
    threat_alerts = serializers.SerializerMethodField()
    action_logs = serializers.SerializerMethodField()
    
    class Meta(UploadedFileSerializer.Meta):
        fields = UploadedFileSerializer.Meta.fields + ['threat_alerts', 'action_logs']

    def get_threat_alerts(self, obj):
        from .models import AIThreatAlert
        alerts = AIThreatAlert.objects.filter(file=obj)
        return AIThreatAlertSerializer(alerts, many=True).data

    def get_action_logs(self, obj):
        logs = FileActionLog.objects.filter(file=obj)
        return FileActionLogSerializer(logs, many=True).data


# =============================================
# ============ File Action Log Serializers ============
# =============================================

class FileActionLogSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    
    class Meta:
        model = FileActionLog
        fields = [
            'id', 'user', 'user_info', 'file', 'file_name',
            'action', 'action_time', 'ip_address', 'user_agent',
            'ai_analysis', 'ai_summary', 'threat_level', 'risk_score'
        ]
        read_only_fields = ['id', 'action_time']

    def get_user_info(self, obj):
        if obj.user:
            return {
                'id': obj.user.id,
                'username': obj.user.username,
                'full_name': f"{obj.user.first_name} {obj.user.last_name}".strip()
            }
        return None


# =============================================
# ============ AI & Security Serializers ============
# =============================================

class AIThreatAlertSerializer(serializers.ModelSerializer):
    file_info = UploadedFileSerializer(read_only=True, source='file')
    reviewed_by_info = UserSerializer(read_only=True, source='reviewed_by')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = AIThreatAlert
        fields = [
            'id', 'file', 'file_info', 'threat_type', 'severity',
            'severity_display', 'description', 'recommended_action',
            'status', 'status_display', 'created_at', 'reviewed_by',
            'reviewed_by_info', 'reviewed_at', 'ai_raw_response'
        ]
        read_only_fields = ['id', 'created_at']


class AINotificationSerializer(serializers.ModelSerializer):
    user_info = UserSerializer(read_only=True, source='user')
    file_info = UploadedFileSerializer(read_only=True, source='file')
    target_users_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = AINotification
        fields = [
            'id', 'title', 'message', 'severity', 'severity_display',
            'status', 'status_display', 'created_at', 'read_at',
            'user', 'user_info', 'file', 'file_info',
            'target_users', 'target_users_info'
        ]
        read_only_fields = ['id', 'created_at']

    def get_target_users_info(self, obj):
        return [{
            'id': u.id,
            'username': u.username,
            'full_name': f"{u.first_name} {u.last_name}".strip()
        } for u in obj.target_users.all()]


# =============================================
# ============ Login Log Serializers ============
# =============================================

class LoginLogSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    user_info = UserSerializer(read_only=True, source='user')
    
    class Meta:
        model = LoginLog
        fields = [
            'id', 'user', 'user_info', 'username', 'ip_address',
            'login_time', 'success', 'user_agent'
        ]
        read_only_fields = ['id', 'login_time']

    def get_username(self, obj):
        return obj.user.username if obj.user else 'Unknown'


# =============================================
# ============ Settings Serializers ============
# =============================================

class UserSettingsSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    
    class Meta:
        model = UserSettings
        fields = [
            'id', 'user', 'user_id', 'font_size', 'menu_size',
            'button_size', 'theme', 'language', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PasswordPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PasswordPolicy
        fields = [
            'id', 'min_password_length', 'require_uppercase',
            'require_digit', 'require_special_char',
            'password_expiry_days', 'max_login_attempts',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AISettingsSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = AISettings
        fields = [
            'id', 'ollama_host', 'ollama_port', 'ollama_model',
            'is_active', 'timeout_seconds', 'max_tokens',
            'temperature', 'top_p', 'frequency_penalty',
            'is_available', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_available(self, obj):
        try:
            from .services.llm_service import llm_service
            return llm_service.is_available if llm_service else False
        except:
            return False


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = [
            'id', 'server_ip', 'server_port', 'allow_remote_access',
            'max_upload_size', 'allowed_file_types', 'enable_security_logs',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# =============================================
# ============ Permission Serializers ============
# =============================================

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type']

class GroupSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permissions_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = [
            'id', 'name', 'permissions', 'permissions_count',
            'user_count'
        ]
        read_only_fields = ['id']

class GroupLeaderSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    leader = UserSerializer(read_only=True)
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group', write_only=True
    )
    leader_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='leader', write_only=True
    )
    
    class Meta:
        model = GroupLeader
        fields = [
            'id', 'group', 'group_id', 'leader', 'leader_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# =============================================
# ============ System Permission Serializers ============
# =============================================

class SystemPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemPermission
        fields = [
            'id', 'name', 'codename', 'description',
            'category', 'is_active'
        ]


class UserPermissionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    permission = SystemPermissionSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    permission_id = serializers.PrimaryKeyRelatedField(
        queryset=SystemPermission.objects.all(), source='permission', write_only=True
    )
    
    class Meta:
        model = UserPermission
        fields = [
            'id', 'user', 'user_id', 'permission', 'permission_id',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# =============================================
# ============ Dashboard & Stats Serializers ============
# =============================================

class DashboardStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_files = serializers.IntegerField()
    total_uploads_today = serializers.IntegerField()
    pending_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    
    class Meta:
        fields = [
            'total_users', 'active_users', 'total_files',
            'total_uploads_today', 'pending_alerts',
            'critical_alerts', 'total_notifications',
            'unread_notifications'
        ]


class FileStatsSerializer(serializers.Serializer):
    total_files = serializers.IntegerField()
    total_size = serializers.IntegerField()
    total_size_readable = serializers.CharField()
    files_by_extension = serializers.DictField()
    files_by_user = serializers.ListField()
    recent_uploads = UploadedFileSerializer(many=True)


class SecurityStatsSerializer(serializers.Serializer):
    total_alerts = serializers.IntegerField()
    pending_alerts = serializers.IntegerField()
    resolved_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    high_alerts = serializers.IntegerField()
    medium_alerts = serializers.IntegerField()
    low_alerts = serializers.IntegerField()
    alerts_by_type = serializers.DictField()
    alerts_by_severity = serializers.DictField()


# =============================================
# ============ Combined Response Serializers ============
# =============================================

class LoginResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    uid = serializers.IntegerField(required=False)
    role = serializers.CharField(required=False)
    token = serializers.CharField(required=False)
    username = serializers.CharField(required=False)
    is_staff = serializers.BooleanField(required=False)
    is_superuser = serializers.BooleanField(required=False)
    msg = serializers.CharField(required=False)


class UploadResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    msg = serializers.CharField()
    uploaded_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    folder_file_count = serializers.IntegerField(required=False)
    threats = serializers.ListField()
    notifications = serializers.ListField()


# =============================================
# ============ Validation Serializers ============
# =============================================

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "رمز عبور جدید و تکرار آن مطابقت ندارند"})
        return data


class FileUploadSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        required=True
    )
    folder_name = serializers.CharField(required=False, default='Unknown')
    folders = serializers.JSONField(required=False, default=list)


class FilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    user_id = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    limit = serializers.IntegerField(required=False, default=20)
    offset = serializers.IntegerField(required=False, default=0)

# =============================================
# ============ Error Serializers ============
# =============================================

class ErrorResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    msg = serializers.CharField()
    errors = serializers.DictField(required=False)
    status_code = serializers.IntegerField(required=False)


class SuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    msg = serializers.CharField()
    data = serializers.JSONField(required=False)