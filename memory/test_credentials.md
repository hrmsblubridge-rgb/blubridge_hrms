# Test Credentials for HRMS Application

## Admin Users
| Role | Username | Password | Access Level |
|------|----------|----------|-------------|
| HR Team | admin | pass123 | Full access to all HR modules |
| System Admin | sysadmin | pass123 | System control + limited HRMS view |
| Office Admin | offadmin | pass123 | View employee data + limited ops |

## Employee Users
| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Employee | user | user | Linked to first seeded employee |
| Employee | spartasolace1 | spar@1230 | spartan (EMP0047), spartasolace@outlook.com |

## Notes
- HR role has full CRUD + approval access
- System Admin can view employees/attendance/leave, manage roles & audit logs
- Office Admin can view employees/attendance/leave/holidays (read-only)
- Employee uses the employee portal with self-service features
