from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.permissions import SYSTEM_PERMISSIONS
from core.models import SystemPermission

class Command(BaseCommand):
    help = 'Initialize system permissions'
    
    def handle(self, *args, **options):
        for code, perm_info in SYSTEM_PERMISSIONS.items():
            obj, created = SystemPermission.objects.get_or_create(
                code=code,
                defaults={
                    'name': perm_info['name'],
                    'description': perm_info.get('description', '')
                }
            )
            if created:
                self.stdout.write(f"✅ ایجاد دسترسی: {perm_info['name']}")
        
        admin_role, _ = Group.objects.get_or_create(name='ادمین سیستم')
        user_role, _ = Group.objects.get_or_create(name='کاربر عادی')
        
        self.stdout.write(self.style.SUCCESS("✅ مقداردهی اولیه دسترسی‌ها کامل شد!"))