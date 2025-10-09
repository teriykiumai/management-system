from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from leaves.models import User, LeaveBalance
from leaves.services.balance_service import calculate_newly_granted_minutes
from leaves.constants import MINUTES_PER_WORK_DAY

class Command(BaseCommand):
    help = '全アクティブユーザーの次年度の休暇残高を計算し、レコードを作成・更新します。'

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help='処理対象の年度（例: 2025）')

    @transaction.atomic
    def handle(self, *args, **options):
        target_year = options['year']
        previous_year = target_year - 1
        self.stdout.write(f"--- {target_year}年度の年次更新バッチを開始します ---")

        active_users = User.objects.filter(is_active=True)
        
        for user in active_users:
            # 1. 前年度の残高レコードを取得
            prev_balance = LeaveBalance.objects.filter(user=user, year=previous_year).first()
            
            # 2. 繰越時間（分）を計算
            carried_over_minutes = 0
            if prev_balance:
                # 繰越上限は20日分
                max_carry_over = 20 * MINUTES_PER_WORK_DAY
                carried_over_minutes = min(prev_balance.total_balance_minutes, max_carry_over)

            # 3. 新規付与時間（分）を計算
            granted_minutes = calculate_newly_granted_minutes(user, target_year)

            # 4. 今年度の残高レコードを作成または更新
            balance, created = LeaveBalance.objects.update_or_create(
                user=user,
                year=target_year,
                defaults={
                    'carried_over_minutes': carried_over_minutes,
                    'granted_minutes': granted_minutes,
                    'used_minutes': 0,
                    'half_leave_used_count': 0,
                    'time_leave_used_minutes': 0,
                }
            )
            status = "作成" if created else "更新"
            self.stdout.write(
                f"  {user}: {status} - 繰越: {carried_over_minutes}分, 新規付与: {granted_minutes}分"
            )

        self.stdout.write(self.style.SUCCESS(f"--- {target_year}年度の年次更新バッチが完了しました ---"))