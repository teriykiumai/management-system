import csv
from pathlib import Path
from typing import List, Dict, Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from leaves.models import (
    Department, Group, Team, Role, Assignment, LeaveBalance,
    BreakTime, Holiday, CompanyLeaveDay, SystemSetting
)

User = get_user_model()

def _to_bool(value: str) -> bool:
    """文字列を真偽値に変換するヘルパー関数"""
    return value.lower() in ['true', '1', 'yes']

class _BaseSeeder:
    """
    Seederの共通処理をまとめた基底クラス.

    Attributes:
        command (BaseCommand): 呼び出し元の管理コマンドインスタンス.
        base_dir (Path): CSVファイルが格納されているディレクトリのパス.
    """
    def __init__(self, command: BaseCommand, base_dir: Path):
        """
        Args:
            command (BaseCommand): ログ出力などに使用するコマンドインスタンス.
            base_dir (Path): CSVデータが置かれているディレクトリパス.
        """
        self.command = command
        self.base_dir = base_dir

    def _read_csv(self, filename: str) -> List[Dict[str, Any]]:
        """
        指定されたCSVファイルを読み込み、辞書のリストとして返す.

        Args:
            filename (str): 読み込むCSVファイル名.

        Returns:
            List[Dict[str, Any]]: CSVの各行を辞書としたリスト.
        """
        filepath = self.base_dir / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            self.command.stdout.write(self.command.style.ERROR(f"  File not found: {filepath}"))
            return []


class OrganizationSeeder(_BaseSeeder):
    """組織・役職関連のマスターデータを投入するSeeder."""

    def clear(self):
        """関連テーブルのデータを全件削除する."""
        Assignment.objects.all().delete()
        Team.objects.all().delete()
        Group.objects.all().delete()
        Department.objects.all().delete()
        Role.objects.all().delete()
        self.command.stdout.write('  Cleared Organization, Role, and Assignment data.')

    def seed(self):
        """組織・役職データをCSVから登録する."""
        # --- 部署・グループ・チーム (依存関係の根元から) ---
        for row in self._read_csv('departments.csv'):
            Department.objects.update_or_create(department_id=row['department_id'], defaults=row)

        for row in self._read_csv('groups.csv'):
            Group.objects.update_or_create(
                group_id=row['group_id'],
                defaults={'group_name': row['group_name'], 'department_id': row['department_id']}
            )

        for row in self._read_csv('teams.csv'):
            Team.objects.update_or_create(
                team_id=row['team_id'],
                defaults={'team_name': row['team_name'], 'group_id': row['group_id']}
            )
        self.command.stdout.write(self.command.style.SUCCESS('    - Organization structure seeded.'))

        # --- 役職 (自己参照FKがあるため2段階で登録) ---
        role_data = self._read_csv('roles.csv')
        # 1. 外部キー以外のフィールドでインスタンスを作成/更新
        for row in role_data:
            order = row.get('approval_order')
            Role.objects.update_or_create(
                role_id=row['role_id'],
                defaults={
                    'role_name': row['role_name'],
                    'role_level': row['role_level'],
                    'view_scope': row['view_scope'],
                    'is_approval_endpoint': _to_bool(row['is_approval_endpoint']),
                    'approval_order': int(order) if order else None,
                }
            )
        # 2. deputy_role (自己参照FK) を設定
        for row in role_data:
            if row.get('deputy_role_id'):
                role = Role.objects.get(role_id=row['role_id'])
                role.deputy_role_id = row['deputy_role_id']
                role.save()
        self.command.stdout.write(self.command.style.SUCCESS('    - Roles seeded.'))


class MasterDataSeeder(_BaseSeeder):
    """祝日・休憩時間などのマスターデータを投入するSeeder."""

    def clear(self):
        """関連テーブルのデータを全件削除する."""
        SystemSetting.objects.all().delete()
        Holiday.objects.all().delete()
        CompanyLeaveDay.objects.all().delete()
        BreakTime.objects.all().delete()
        self.command.stdout.write('  Cleared SystemSettings, Holidays, CompanyLeaveDays, BreakTimes.')
        
    def seed(self):
        """各種マスターデータをCSVから登録する."""
        for row in self._read_csv('system_settings.csv'):
            SystemSetting.objects.update_or_create(year=row['year'], defaults=row)
        self.command.stdout.write(self.command.style.SUCCESS('    - SystemSettings seeded.'))

        for row in self._read_csv('holidays.csv'):
            Holiday.objects.update_or_create(holiday_date=row['holiday_date'], defaults=row)
        self.command.stdout.write(self.command.style.SUCCESS('    - Holidays seeded.'))

        for row in self._read_csv('company_leave_days.csv'):
            defaults = {k: v for k, v in row.items() if k != 'day_id'}
            defaults['is_active'] = _to_bool(defaults.get('is_active', 'false'))
            CompanyLeaveDay.objects.update_or_create(day_id=row['day_id'], defaults=defaults)
        self.command.stdout.write(self.command.style.SUCCESS('    - CompanyLeaveDays seeded.'))
        
        for row in self._read_csv('break_times.csv'):
            user_id = row.get('user_id')
            dept_id = row.get('department_id')
            BreakTime.objects.update_or_create(
                break_time_id=row['break_time_id'],
                defaults={
                    'user_id': user_id if user_id else None,
                    'department_id': dept_id if dept_id else None,
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'description': row['description'],
                }
            )
        self.command.stdout.write(self.command.style.SUCCESS('    - BreakTimes seeded.'))


class UserDataSeeder(_BaseSeeder):
    """ユーザー関連データ（ユーザー、所属、休暇残高）を投入するSeeder."""

    def clear(self):
        """関連テーブルのデータを全件削除する（スーパーユーザーは除く）."""
        # 外部キー制約のため、依存している側から削除
        LeaveBalance.objects.all().delete()
        Assignment.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.command.stdout.write('  Cleared LeaveBalances, Assignments, and non-superuser Users.')
    
    def seed_users(self):
        """ユーザーデータを登録する."""
        for row in self._read_csv('users.csv'):
            user, created = User.objects.update_or_create(
                employee_id=row['employee_id'],
                defaults={
                    'last_name': row['last_name'],
                    'first_name': row['first_name'],
                    'email': row['email'],
                    'hire_date': row['hire_date'] or None,
                }
            )
            # パスワードは毎回設定する
            user.set_password(row['password'])
            user.save()
        self.command.stdout.write(self.command.style.SUCCESS('    - Users seeded.'))

    def seed_assignments(self):
        """所属情報を登録する."""
        for row in self._read_csv('assignments.csv'):
            group_id = row.get('group_id')
            team_id = row.get('team_id')
            Assignment.objects.update_or_create(
                assignment_id=row['assignment_id'],
                defaults={
                    'user': User.objects.get(employee_id=row['user_id']),
                    'department_id': row['department_id'],
                    'group_id': int(group_id) if group_id else None,
                    'team_id': int(team_id) if team_id else None,
                    'role_id': row['role_id'],
                    'is_primary': _to_bool(row['is_primary']),
                }
            )
        self.command.stdout.write(self.command.style.SUCCESS('    - Assignments seeded.'))

    def seed_leave_balances(self):
        """休暇残高を登録する."""
        for row in self._read_csv('leave_balances.csv'):
            defaults = {
                'carried_over_minutes': int(row['carried_over_minutes']),
                'granted_minutes': int(row['granted_minutes']),
                'used_minutes': int(row['used_minutes']),
                'half_leave_used_count': int(row['half_leave_used_count']),
                'time_leave_used_minutes': int(row['time_leave_used_minutes']),
            }
            LeaveBalance.objects.update_or_create(
                user=User.objects.get(employee_id=row['user_id']),
                year=int(row['year']),
                defaults=defaults
            )
        self.command.stdout.write(self.command.style.SUCCESS('    - LeaveBalances seeded.'))