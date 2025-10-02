from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from leaves.models import Application, TimeLeaveSlot, ApprovalHistory
from leaves.services.seeding import (
    OrganizationSeeder, MasterDataSeeder, UserDataSeeder
)

class Command(BaseCommand):
    """
    開発用に、マスターデータとサンプルユーザーをデータベースに登録する.
    
    CSVファイルはプロジェクトルートの 'master_data' ディレクトリに配置する必要があります.
    このコマンドを実行すると、関連する既存のデータは一度すべて削除されます.
    """
    help = 'Seed the database with all master data and sample users'

    @transaction.atomic
    def handle(self, *args: Any, **options: Any):
        """コマンド実行のメインロジック."""
        self.stdout.write(self.style.SUCCESS('--- Database Seeding Start ---'))
        
        # プロジェクトルート/master_data ディレクトリへのパスを構築
        base_dir = Path(__file__).resolve().parent.parent.parent.parent / 'master_data'
        if not base_dir.exists():
            raise CommandError(f"Master data directory not found at: {base_dir}")

        # Seederクラスをインスタンス化
        org_seeder = OrganizationSeeder(self, base_dir)
        master_seeder = MasterDataSeeder(self, base_dir)
        user_data_seeder = UserDataSeeder(self, base_dir)

        # ---------------------------------------------------------------------
        # 1. データのクリア (外部キーの依存関係が強いモデルから順に削除)
        # ---------------------------------------------------------------------
        self.stdout.write('Clearing old data...')
        
        # 申請関連データ (多くのモデルに依存)
        TimeLeaveSlot.objects.all().delete()
        ApprovalHistory.objects.all().delete()
        Application.objects.all().delete()
        
        # ユーザー関連データ (seederのclearメソッドを呼び出し)
        user_data_seeder.clear()
        
        # 組織・役職データ
        org_seeder.clear()
        
        # その他マスターデータ
        master_seeder.clear()
        
        self.stdout.write(self.style.SUCCESS('  All old data cleared.'))

        # ---------------------------------------------------------------------
        # 2. データの登録 (依存関係がないモデルから順に登録)
        # ---------------------------------------------------------------------
        self.stdout.write('Seeding new data...')
        
        # 組織・役職データ
        org_seeder.seed()
        
        # その他マスターデータ
        master_seeder.seed()
        
        # ユーザー関連データ (依存関係順にメソッドを呼び出し)
        user_data_seeder.seed_users()
        user_data_seeder.seed_assignments()
        user_data_seeder.seed_leave_balances()

        self.stdout.write(self.style.SUCCESS('--- Database Seeding Complete! ---'))