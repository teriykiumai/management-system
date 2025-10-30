from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model
from leaves.models import Department, Group, Team, Role, Assignment
from leaves.services.approval_route_service import generate_approval_route

User = get_user_model()

class ApprovalRouteServiceTest(TestCase):
    """approval_route_service のテスト"""

    def setUp(self):
        """テスト全体で共通して使用するデータを準備"""
        # Arrange (準備): 組織構造と役職を作成
        self.dep_dev = Department.objects.create(department_name="技術部")
        self.dep_ops = Department.objects.create(department_name="業務部")
        self.group = Group.objects.create(group_name="システム開発G", department=self.dep_dev)
        self.team = Team.objects.create(team_name="アプリ開発T", group=self.group)

        self.role_staff = Role.objects.create(role_name="一般社員", role_level=10)
        self.role_tl = Role.objects.create(role_name="チームリーダー", role_level=20, approval_order=1)
        self.role_gl = Role.objects.create(role_name="グループ長", role_level=30, approval_order=2)
        self.role_final = Role.objects.create(role_name="業務部・勤怠管理担当", role_level=80)

    def test_generate_simple_route(self):
        """一次承認者(TL)と二次承認者(GL)がいる場合の基本的なルート生成をテスト"""
        # Arrange (準備): このテストケース専用のユーザーと所属を作成
        applicant = User.objects.create_user(employee_id="e0001", last_name="申請", first_name="太郎")
        team_leader = User.objects.create_user(employee_id="e0002", last_name="承認", first_name="一郎")
        group_leader = User.objects.create_user(employee_id="e0003", last_name="承認", first_name="次郎")
        final_approver = User.objects.create_user(employee_id="e9999", last_name="業務部", first_name="担当")

        applicant_assignment = Assignment.objects.create(
            user=applicant, department=self.dep_dev, group=self.group, team=self.team, role=self.role_staff, is_primary=True
        )
        Assignment.objects.create(
            user=team_leader, department=self.dep_dev, group=self.group, team=self.team, role=self.role_tl
        )
        Assignment.objects.create(
            user=group_leader, department=self.dep_dev, group=self.group, role=self.role_gl
        )
        Assignment.objects.create(user=final_approver, department=self.dep_ops, role=self.role_final)

        # Act (実行): 承認ルート生成サービスを呼び出す
        approval_route = generate_approval_route(applicant_assignment, date.today())

        # Assert (検証): 結果が期待通りかチェック
        self.assertEqual(len(approval_route), 3) # 承認者が3人いるか
        self.assertEqual(approval_route[0], team_leader) # 1人目はチームリーダーか
        self.assertEqual(approval_route[1], group_leader) # 2人目はグループ長か
        self.assertEqual(approval_route[2], final_approver) # 3人目は最終承認者か

# --- ここに他のテストケース（例：GLがいない場合など）を追加していく ---