from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from datasets.models import Dataset
from employees.models import Department, EmployeeProfile, Role, RoleDepartment

User = get_user_model()


def make_user(email, first_name="", last_name="", is_staff=False):
    user = User.objects.create_user(
        email=email, password="testpass123",
        first_name=first_name, last_name=last_name,
    )
    if is_staff:
        user.is_staff = True
        user.save()
    return user


class WorkflowTestCase(APITestCase):
    """End-to-end creator -> reviewer -> approver workflow tests."""

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="FINANCE")
        cls.creator_role = Role.objects.create(name="TABLE_CREATOR", can_create=True, can_edit=True, can_view=True)
        cls.reviewer_role = Role.objects.create(name="TABLE_REVIEWER", can_review=True, can_view=True)
        cls.approver_role = Role.objects.create(name="TABLE_APPROVER", can_approve=True, can_view=True)

        for role in (cls.creator_role, cls.reviewer_role, cls.approver_role):
            RoleDepartment.objects.create(
                role=role, department=cls.department, modules=["finance"]
            )

        cls.creator = make_user("creator@example.com", "Cre", "ator")
        cls.reviewer = make_user("reviewer@example.com", "Rev", "iewer")
        cls.approver = make_user("approver@example.com", "App", "rover")
        cls.bystander = make_user("bystander@example.com")

        for user, role in (
            (cls.creator, cls.creator_role),
            (cls.reviewer, cls.reviewer_role),
            (cls.approver, cls.approver_role),
        ):
            profile = EmployeeProfile.objects.create(
                user=user,
                department=cls.department,
                job_title="Analyst",
                status="ACTIVE",
            )
            profile.roles.add(role)

        cls.dataset = Dataset.objects.create(
            name="budget_2026",
            original_filename="budget_2026.csv",
            table_name="dummy_table",
            row_count=0,
            status="draft",
            section="finance",
            created_by=cls.creator,
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _post(self, action, pk=None, data=None):
        dataset_id = pk if pk is not None else self.dataset.pk
        url = reverse(action, kwargs={"pk": dataset_id})
        return self.client.post(url, data or {}, format="json")

    def test_creator_cannot_review_or_approve_own_table(self):
        self._auth(self.creator)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "submitted")

        resp = self._post("start-review")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_happy_path_creator_reviewer_approver(self):
        self._auth(self.creator)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "submitted")
        self.assertEqual(self.dataset.submitted_by, self.creator)

        self._auth(self.reviewer)
        resp = self._post("start-review")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "in_review")

        resp = self._post("review-approve", data={"comment": "Looks good"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "reviewed")
        self.assertEqual(self.dataset.reviewed_by, self.reviewer)
        self.assertEqual(self.dataset.review_comment, "Looks good")

        self._auth(self.approver)
        resp = self._post("approve", data={"comment": "Confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "confirmed")
        self.assertEqual(self.dataset.approved_by, self.approver)
        self.assertEqual(self.dataset.approval_comment, "Confirmed")

    def test_illegal_transitions_rejected(self):
        self._auth(self.approver)
        resp = self._post("approve")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

        self._auth(self.reviewer)
        resp = self._post("review-approve")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

        self._auth(self.creator)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_reject_returns_to_rejected_and_creator_resubmits(self):
        self._auth(self.creator)
        self._post("submit")

        self._auth(self.reviewer)
        self._post("start-review")
        resp = self._post("reject", data={"comment": "Fix totals"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "rejected")
        self.assertEqual(self.dataset.rejection_comment, "Fix totals")

        self._auth(self.creator)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, "submitted")

    def test_bystander_without_role_denied(self):
        self._auth(self.bystander)
        resp = self._post("submit")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_role_scoped_to_module_denied_other_module(self):
        # Reviewer's RoleDepartment only covers 'finance'. Create an IT dataset
        # and confirm the reviewer cannot act on it.
        it_dataset = Dataset.objects.create(
            name="it_assets",
            original_filename="it_assets.csv",
            table_name="dummy_it_table",
            row_count=0,
            status="submitted",
            section="it",
            created_by=self.creator,
        )
        self._auth(self.reviewer)
        resp = self._post("start-review", pk=it_dataset.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
