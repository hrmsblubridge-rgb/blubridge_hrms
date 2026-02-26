from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import hashlib
import cloudinary
import cloudinary.utils
import cloudinary.uploader
import resend
import time

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Indian Standard Time (IST) - UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current datetime in Indian Standard Time"""
    return datetime.now(IST)

def get_ist_today():
    """Get today's date string in IST (format: DD-MM-YYYY)"""
    return get_ist_now().strftime("%d-%m-%Y")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'blubridge-hrms-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# Resend Configuration
resend.api_key = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

# Create the main app
app = FastAPI(title="BluBridge HRMS API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== ENUMS ==============

class UserRole:
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    HR_MANAGER = "hr_manager"
    TEAM_LEAD = "team_lead"
    EMPLOYEE = "employee"

class EmploymentType:
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERN = "Intern"

class EmployeeStatus:
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    RESIGNED = "Resigned"

class TierLevel:
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"

class WorkLocation:
    REMOTE = "Remote"
    OFFICE = "Office"
    HYBRID = "Hybrid"

# ============== SHIFT CONFIGURATION ==============

# Predefined shift timings (24-hour format for calculations)
SHIFT_DEFINITIONS = {
    "General": {
        "login_time": "10:00",  # 10:00 AM
        "logout_time": "21:00",  # 9:00 PM
        "total_hours": 11,
        "description": "Standard shift (10:00 AM - 9:00 PM)"
    },
    "Morning": {
        "login_time": "06:00",  # 6:00 AM
        "logout_time": "14:00",  # 2:00 PM
        "total_hours": 8,
        "description": "Morning shift (6:00 AM - 2:00 PM)"
    },
    "Evening": {
        "login_time": "14:00",  # 2:00 PM
        "logout_time": "22:00",  # 10:00 PM
        "total_hours": 8,
        "description": "Evening shift (2:00 PM - 10:00 PM)"
    },
    "Night": {
        "login_time": "22:00",  # 10:00 PM
        "logout_time": "06:00",  # 6:00 AM (next day)
        "total_hours": 8,
        "description": "Night shift (10:00 PM - 6:00 AM)"
    },
    "Flexible": {
        "login_time": None,  # No fixed time
        "logout_time": None,
        "total_hours": 8,
        "description": "Flexible shift (8 hours required, no fixed time)"
    },
    "Custom": {
        "login_time": None,  # Set by admin per employee
        "logout_time": None,
        "total_hours": None,  # Auto-calculated
        "description": "Custom shift (admin-defined timings)"
    }
}

class AttendanceStatus:
    PRESENT = "Present"
    LATE_LOGIN = "Late Login"
    EARLY_OUT = "Early Out"
    LOSS_OF_PAY = "Loss of Pay"
    LEAVE = "Leave"
    ABSENT = "Absent"
    NOT_LOGGED = "Not Logged"
    LOGIN = "Login"
    COMPLETED = "Completed"

# ============== ONBOARDING ENUMS ==============

class OnboardingStatus:
    PENDING = "pending"  # Employee created, not started onboarding
    IN_PROGRESS = "in_progress"  # Employee has started uploading docs
    UNDER_REVIEW = "under_review"  # All docs submitted, awaiting HR review
    APPROVED = "approved"  # HR approved, full HRMS access granted
    REJECTED = "rejected"  # HR rejected, needs re-upload

class DocumentStatus:
    NOT_UPLOADED = "not_uploaded"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    REJECTED = "rejected"

class DocumentType:
    AADHAAR_CARD = "aadhaar_card"
    PAN_CARD = "pan_card"
    PASSPORT = "passport"
    VOTER_ID = "voter_id"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    OFFER_LETTER = "offer_letter"
    RELIEVING_LETTER = "relieving_letter"
    PHOTO = "photo"

REQUIRED_DOCUMENTS = [
    {"type": DocumentType.AADHAAR_CARD, "label": "Aadhaar Card", "required": True},
    {"type": DocumentType.PAN_CARD, "label": "PAN Card", "required": True},
    {"type": DocumentType.PASSPORT, "label": "Passport", "required": False},
    {"type": DocumentType.VOTER_ID, "label": "Voter ID", "required": False},
    {"type": DocumentType.EDUCATION, "label": "Education Certificates", "required": True},
    {"type": DocumentType.EXPERIENCE, "label": "Experience Certificates", "required": False},
    {"type": DocumentType.OFFER_LETTER, "label": "Offer / Appointment Letter", "required": False},
    {"type": DocumentType.RELIEVING_LETTER, "label": "Relieving Letter", "required": False},
    {"type": DocumentType.PHOTO, "label": "Passport-size Photograph", "required": True},
]

# ============== MODELS ==============

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    name: str
    role: str = UserRole.EMPLOYEE
    employee_id: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    onboarding_status: str = OnboardingStatus.PENDING  # NEW: Track onboarding state
    is_first_login: bool = True  # NEW: Track if first login
    created_at: datetime = Field(default_factory=lambda: get_ist_now())
    is_active: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

# Comprehensive Employee Model
class Employee(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Personal Information
    emp_id: str  # Auto-generated
    full_name: str
    official_email: str
    phone_number: Optional[str] = None
    gender: Optional[str] = None  # Male, Female, Other
    date_of_birth: Optional[str] = None
    
    # Employment Information
    date_of_joining: str
    employment_type: str = EmploymentType.FULL_TIME
    employee_status: str = EmployeeStatus.ACTIVE
    designation: str
    tier_level: str = TierLevel.MID
    reporting_manager_id: Optional[str] = None
    
    # Organization Structure
    department: str
    team: str
    work_location: str = WorkLocation.OFFICE
    
    # HR Configuration
    leave_policy: Optional[str] = "Standard"
    shift_type: Optional[str] = "General"
    attendance_tracking_enabled: bool = True
    
    # Custom Shift Configuration (only for shift_type = "Custom")
    custom_login_time: Optional[str] = None  # Format: "HH:MM" (24-hour)
    custom_logout_time: Optional[str] = None  # Format: "HH:MM" (24-hour)
    custom_total_hours: Optional[float] = None  # Auto-calculated from times
    
    # Salary Configuration (for payroll)
    monthly_salary: Optional[float] = 0.0
    
    # System Access
    user_role: str = UserRole.EMPLOYEE
    login_enabled: bool = True
    
    # Legacy fields for compatibility
    avatar: Optional[str] = None
    stars: int = 0
    unsafe_count: int = 0
    
    # Onboarding fields
    onboarding_status: str = OnboardingStatus.PENDING
    onboarding_completed_at: Optional[datetime] = None
    
    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: get_ist_now())
    updated_at: datetime = Field(default_factory=lambda: get_ist_now())

class EmployeeCreate(BaseModel):
    # Personal Information
    full_name: str
    official_email: str
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    
    # Employment Information
    date_of_joining: str
    employment_type: str = EmploymentType.FULL_TIME
    designation: str
    tier_level: str = TierLevel.MID
    reporting_manager_id: Optional[str] = None
    
    # Organization Structure
    department: str
    team: str
    work_location: str = WorkLocation.OFFICE
    
    # HR Configuration
    leave_policy: Optional[str] = "Standard"
    shift_type: Optional[str] = "General"
    attendance_tracking_enabled: bool = True
    
    # Custom Shift Configuration
    custom_login_time: Optional[str] = None
    custom_logout_time: Optional[str] = None
    custom_total_hours: Optional[float] = None
    
    # Salary Configuration
    monthly_salary: Optional[float] = 0.0
    
    # System Access
    user_role: str = UserRole.EMPLOYEE
    login_enabled: bool = True

class EmployeeUpdate(BaseModel):
    # Personal Information
    full_name: Optional[str] = None
    official_email: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    
    # Employment Information
    date_of_joining: Optional[str] = None
    employment_type: Optional[str] = None
    employee_status: Optional[str] = None
    designation: Optional[str] = None
    tier_level: Optional[str] = None
    reporting_manager_id: Optional[str] = None
    
    # Organization Structure
    department: Optional[str] = None
    team: Optional[str] = None
    work_location: Optional[str] = None
    
    # HR Configuration
    leave_policy: Optional[str] = None
    shift_type: Optional[str] = None
    attendance_tracking_enabled: Optional[bool] = None
    
    # Custom Shift Configuration
    custom_login_time: Optional[str] = None
    custom_logout_time: Optional[str] = None
    custom_total_hours: Optional[float] = None
    
    # Salary Configuration
    monthly_salary: Optional[float] = None
    
    # System Access
    user_role: Optional[str] = None
    login_enabled: Optional[bool] = None

class Attendance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    emp_name: str
    team: str
    department: str
    date: str
    check_in: Optional[str] = None  # Time in "HH:MM AM/PM" format
    check_out: Optional[str] = None  # Time in "HH:MM AM/PM" format
    check_in_24h: Optional[str] = None  # Time in "HH:MM" 24-hour format for calculations
    check_out_24h: Optional[str] = None  # Time in "HH:MM" 24-hour format for calculations
    total_hours: Optional[str] = None
    total_hours_decimal: Optional[float] = None  # For precise calculations
    status: str = "Not Logged"
    is_lop: bool = False  # Loss of Pay flag
    lop_reason: Optional[str] = None  # Reason for LOP
    shift_type: Optional[str] = "General"  # Employee's shift at time of attendance
    expected_login: Optional[str] = None  # Expected login time based on shift
    expected_logout: Optional[str] = None  # Expected logout time based on shift
    created_at: datetime = Field(default_factory=lambda: get_ist_now())

class LeaveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    emp_name: str
    team: str
    department: str
    leave_type: str
    start_date: str
    end_date: str
    duration: str
    reason: Optional[str] = None
    status: str = "pending"
    approved_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: get_ist_now())

class LeaveRequestCreate(BaseModel):
    employee_id: str
    leave_type: str
    start_date: str
    end_date: str
    reason: Optional[str] = None

class StarReward(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    stars: int
    reason: str
    type: str = "performance"  # performance, learning, innovation, unsafe
    awarded_by: str
    month: str
    created_at: datetime = Field(default_factory=lambda: get_ist_now())

class StarRewardCreate(BaseModel):
    employee_id: str
    stars: int
    reason: str
    type: str = "performance"

class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    department: str
    lead_id: Optional[str] = None
    member_count: int = 0
    created_at: datetime = Field(default_factory=lambda: get_ist_now())

class Department(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    head_id: Optional[str] = None
    team_count: int = 0

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: get_ist_now())

# ============== PAYROLL MODEL ==============

class PayrollRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    emp_name: str
    department: str
    team: str
    month: str  # Format: "YYYY-MM"
    monthly_salary: float = 0.0
    working_days: int = 0  # Total working days in month (excluding Sundays)
    present_days: int = 0
    lop_days: int = 0
    leave_days: int = 0
    absent_days: int = 0
    per_day_salary: float = 0.0
    lop_deduction: float = 0.0
    net_salary: float = 0.0
    attendance_details: List[dict] = []  # Daily attendance breakdown
    created_at: datetime = Field(default_factory=lambda: get_ist_now())
    updated_at: datetime = Field(default_factory=lambda: get_ist_now())

class ShiftConfigCreate(BaseModel):
    shift_type: str
    login_time: Optional[str] = None  # For custom shifts
    logout_time: Optional[str] = None  # For custom shifts

# ============== ONBOARDING MODELS ==============

class OnboardingDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    document_type: str
    document_label: str
    file_url: Optional[str] = None
    file_public_id: Optional[str] = None
    file_name: Optional[str] = None
    status: str = DocumentStatus.NOT_UPLOADED
    uploaded_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: get_ist_now())

class OnboardingRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    emp_id: str
    emp_name: str
    department: str
    team: str
    designation: str
    status: str = OnboardingStatus.PENDING
    documents: List[dict] = []  # List of document statuses
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: get_ist_now())
    updated_at: datetime = Field(default_factory=lambda: get_ist_now())

class DocumentUpload(BaseModel):
    document_type: str
    file_url: str
    file_public_id: Optional[str] = None
    file_name: Optional[str] = None

class DocumentVerification(BaseModel):
    document_id: str
    status: str  # "verified" or "rejected"
    rejection_reason: Optional[str] = None

class OnboardingApproval(BaseModel):
    status: str  # "approved" or "rejected"
    review_notes: Optional[str] = None

class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "medium"  # low, medium, high

class Ticket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    emp_name: str
    department: str
    subject: str
    description: str
    priority: str = "medium"
    status: str = "open"  # open, in_progress, resolved, closed
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: get_ist_now())
    updated_at: datetime = Field(default_factory=lambda: get_ist_now())
    resolved_at: Optional[datetime] = None

# ============== HELPERS ==============

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def log_audit(user_id: str, action: str, resource: str, resource_id: str = None, details: str = None):
    log = AuditLog(user_id=user_id, action=action, resource=resource, resource_id=resource_id, details=details)
    doc = log.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.audit_logs.insert_one(doc.copy())

def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    if 'created_at' in doc and not isinstance(doc['created_at'], str):
        doc['created_at'] = doc['created_at'].isoformat()
    if 'updated_at' in doc and not isinstance(doc['updated_at'], str):
        doc['updated_at'] = doc['updated_at'].isoformat()
    if 'deleted_at' in doc and doc['deleted_at'] and not isinstance(doc['deleted_at'], str):
        doc['deleted_at'] = doc['deleted_at'].isoformat()
    if 'timestamp' in doc and not isinstance(doc['timestamp'], str):
        doc['timestamp'] = doc['timestamp'].isoformat()
    return doc

async def generate_emp_id():
    """Generate unique employee ID"""
    count = await db.employees.count_documents({})
    return f"EMP{str(count + 1).zfill(4)}"

# ============== SHIFT & LOP CALCULATION HELPERS ==============

def parse_time_12h_to_24h(time_str: str) -> str:
    """Convert 12-hour format (e.g., '10:00 AM') to 24-hour format (e.g., '10:00')"""
    if not time_str:
        return None
    try:
        time_str = time_str.strip().upper()
        if 'AM' in time_str or 'PM' in time_str:
            dt = datetime.strptime(time_str.replace(' ', ''), "%I:%M%p")
            return dt.strftime("%H:%M")
        return time_str  # Already in 24h format
    except:
        return None

def parse_time_24h_to_minutes(time_str: str) -> int:
    """Convert 24-hour time string to minutes since midnight"""
    if not time_str:
        return None
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return None

def minutes_to_time_24h(minutes: int) -> str:
    """Convert minutes since midnight to 24-hour time string"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def get_shift_timings(employee: dict) -> dict:
    """Get shift timings for an employee based on their shift type"""
    shift_type = employee.get('shift_type', 'General')
    
    if shift_type == "Custom":
        login_time = employee.get('custom_login_time')
        logout_time = employee.get('custom_logout_time')
        
        if login_time and logout_time:
            login_mins = parse_time_24h_to_minutes(login_time)
            logout_mins = parse_time_24h_to_minutes(logout_time)
            
            # Handle overnight shifts
            if logout_mins < login_mins:
                total_hours = (24 * 60 - login_mins + logout_mins) / 60
            else:
                total_hours = (logout_mins - login_mins) / 60
            
            return {
                "login_time": login_time,
                "logout_time": logout_time,
                "total_hours": total_hours
            }
        return None
    
    shift_def = SHIFT_DEFINITIONS.get(shift_type, SHIFT_DEFINITIONS["General"])
    return {
        "login_time": shift_def["login_time"],
        "logout_time": shift_def["logout_time"],
        "total_hours": shift_def["total_hours"]
    }

def calculate_attendance_status(check_in_24h: str, check_out_24h: str, shift_timings: dict) -> dict:
    """
    Calculate attendance status based on strict LOP rules:
    - Late login (even 1 minute) = LOP
    - Early logout (even 1 minute) = LOP
    - Insufficient hours = LOP
    - No grace period
    """
    result = {
        "status": AttendanceStatus.PRESENT,
        "is_lop": False,
        "lop_reason": None,
        "total_hours_decimal": 0.0
    }
    
    # Flexible shift - only check total hours
    if shift_timings.get("login_time") is None:
        if check_in_24h and check_out_24h:
            in_mins = parse_time_24h_to_minutes(check_in_24h)
            out_mins = parse_time_24h_to_minutes(check_out_24h)
            
            if out_mins < in_mins:
                total_mins = 24 * 60 - in_mins + out_mins
            else:
                total_mins = out_mins - in_mins
            
            result["total_hours_decimal"] = total_mins / 60
            required_hours = shift_timings.get("total_hours", 8)
            
            if result["total_hours_decimal"] < required_hours:
                result["status"] = AttendanceStatus.LOSS_OF_PAY
                result["is_lop"] = True
                result["lop_reason"] = f"Insufficient hours: {result['total_hours_decimal']:.2f}h < {required_hours}h required"
        return result
    
    # Fixed shift - strict rules apply
    expected_login = parse_time_24h_to_minutes(shift_timings["login_time"])
    expected_logout = parse_time_24h_to_minutes(shift_timings["logout_time"])
    required_hours = shift_timings["total_hours"]
    
    if not check_in_24h:
        result["status"] = AttendanceStatus.NOT_LOGGED
        return result
    
    actual_login = parse_time_24h_to_minutes(check_in_24h)
    
    # Check for late login (STRICT - even 1 minute late = LOP)
    if actual_login > expected_login:
        late_mins = actual_login - expected_login
        result["status"] = AttendanceStatus.LOSS_OF_PAY
        result["is_lop"] = True
        result["lop_reason"] = f"Late login by {late_mins} minute(s). Expected: {shift_timings['login_time']}, Actual: {check_in_24h}"
        
        # Still calculate hours if checked out
        if check_out_24h:
            actual_logout = parse_time_24h_to_minutes(check_out_24h)
            if actual_logout < actual_login:
                total_mins = 24 * 60 - actual_login + actual_logout
            else:
                total_mins = actual_logout - actual_login
            result["total_hours_decimal"] = total_mins / 60
        return result
    
    # Check for early logout (STRICT - even 1 minute early = LOP)
    if check_out_24h:
        actual_logout = parse_time_24h_to_minutes(check_out_24h)
        
        # Calculate total hours
        if actual_logout < actual_login:
            total_mins = 24 * 60 - actual_login + actual_logout
        else:
            total_mins = actual_logout - actual_login
        result["total_hours_decimal"] = total_mins / 60
        
        if actual_logout < expected_logout:
            early_mins = expected_logout - actual_logout
            result["status"] = AttendanceStatus.LOSS_OF_PAY
            result["is_lop"] = True
            result["lop_reason"] = f"Early logout by {early_mins} minute(s). Expected: {shift_timings['logout_time']}, Actual: {check_out_24h}"
            return result
        
        # Check total hours requirement
        if result["total_hours_decimal"] < required_hours:
            result["status"] = AttendanceStatus.LOSS_OF_PAY
            result["is_lop"] = True
            result["lop_reason"] = f"Insufficient hours: {result['total_hours_decimal']:.2f}h < {required_hours}h required"
            return result
        
        # All conditions met - Present
        result["status"] = AttendanceStatus.PRESENT
    else:
        # Only logged in, not logged out yet
        result["status"] = AttendanceStatus.LOGIN
    
    return result

def calculate_total_hours_str(total_hours_decimal: float) -> str:
    """Convert decimal hours to string format (e.g., '8h 30m')"""
    if not total_hours_decimal:
        return "-"
    hours = int(total_hours_decimal)
    minutes = int((total_hours_decimal - hours) * 60)
    return f"{hours}h {minutes}m"

async def calculate_payroll_for_employee(employee_id: str, month: str) -> dict:
    """
    Calculate payroll for an employee for a given month.
    Month format: "YYYY-MM"
    """
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        return None
    
    year, month_num = map(int, month.split('-'))
    
    # Get number of days in month and working days (excluding Sundays)
    import calendar
    days_in_month = calendar.monthrange(year, month_num)[1]
    
    working_days = 0
    for day in range(1, days_in_month + 1):
        date_obj = datetime(year, month_num, day)
        if date_obj.weekday() != 6:  # Not Sunday
            working_days += 1
    
    # Get attendance records for the month
    from_date = f"01-{month_num:02d}-{year}"
    to_date = f"{days_in_month:02d}-{month_num:02d}-{year}"
    
    attendance_records = await db.attendance.find({
        "employee_id": employee_id,
        "date": {"$gte": from_date, "$lte": to_date}
    }, {"_id": 0}).to_list(days_in_month)
    
    # Get leave records for the month
    leave_records = await db.leaves.find({
        "employee_id": employee_id,
        "status": "approved",
        "$or": [
            {"start_date": {"$regex": f"^{year}-{month_num:02d}"}},
            {"end_date": {"$regex": f"^{year}-{month_num:02d}"}}
        ]
    }, {"_id": 0}).to_list(100)
    
    # Build attendance map
    attendance_map = {}
    for record in attendance_records:
        attendance_map[record["date"]] = record
    
    # Calculate days (lop_days is float to support 0.5 day calculations)
    present_days = 0
    lop_days = 0.0  # Float to support half-day LOP
    leave_days = 0
    absent_days = 0
    attendance_details = []
    
    for day in range(1, days_in_month + 1):
        date_obj = datetime(year, month_num, day)
        date_str = f"{day:02d}-{month_num:02d}-{year}"
        
        detail = {
            "date": date_str,
            "day_name": date_obj.strftime("%a"),
            "is_sunday": date_obj.weekday() == 6,
            "status": "NA",
            "is_lop": False,
            "check_in": None,
            "check_out": None,
            "total_hours": None
        }
        
        if date_obj.weekday() == 6:  # Sunday
            detail["status"] = "Sunday"
            attendance_details.append(detail)
            continue
        
        record = attendance_map.get(date_str)
        
        if record:
            detail["check_in"] = record.get("check_in")
            detail["check_out"] = record.get("check_out")
            detail["total_hours"] = record.get("total_hours")
            detail["status"] = record.get("status", "NA")
            detail["is_lop"] = record.get("is_lop", False)
            detail["lop_value"] = 0  # Default: no LOP
            
            status = record.get("status", "NA")
            is_lop = record.get("is_lop", False)
            
            # Full day LOP: is_lop flag or Loss of Pay status (late + early out combined)
            if is_lop or status == "Loss of Pay":
                lop_days += 1
                detail["lop_value"] = 1
            # Half day LOP: Late Login only OR Early Out only (without is_lop flag)
            elif status in [AttendanceStatus.LATE_LOGIN, "Late Login"]:
                lop_days += 0.5
                detail["is_lop"] = True
                detail["lop_value"] = 0.5
            elif status in [AttendanceStatus.EARLY_OUT, "Early Out"]:
                lop_days += 0.5
                detail["is_lop"] = True
                detail["lop_value"] = 0.5
            # Present: no LOP
            elif status in [AttendanceStatus.PRESENT, AttendanceStatus.COMPLETED, "Present", "Completed"]:
                present_days += 1
            # Leave
            elif status == AttendanceStatus.LEAVE or status == "Leave":
                leave_days += 1
            # Not logged / NA
            elif status in [AttendanceStatus.NOT_LOGGED, "Not Logged", "NA"]:
                absent_days += 1
            else:
                present_days += 1
        else:
            detail["status"] = "Absent"
            absent_days += 1
        
        attendance_details.append(detail)
    
    # Calculate salary
    monthly_salary = employee.get("monthly_salary", 0.0) or 0.0
    per_day_salary = monthly_salary / 30 if monthly_salary > 0 else 0  # Standard 30-day calculation
    lop_deduction = per_day_salary * (lop_days + absent_days)
    net_salary = monthly_salary - lop_deduction
    
    return {
        "employee_id": employee_id,
        "emp_name": employee.get("full_name"),
        "emp_id": employee.get("emp_id"),
        "department": employee.get("department"),
        "team": employee.get("team"),
        "shift_type": employee.get("shift_type"),
        "month": month,
        "monthly_salary": monthly_salary,
        "working_days": working_days,
        "present_days": present_days,
        "lop_days": lop_days,  # Now can be decimal (e.g., 2.5)
        "leave_days": leave_days,
        "absent_days": absent_days,
        "per_day_salary": round(per_day_salary, 2),
        "lop_deduction": round(lop_deduction, 2),
        "net_salary": round(max(0, net_salary), 2),
        "attendance_details": attendance_details
    }

# ============== EMAIL HELPERS ==============

async def send_email_notification(to_email: str, subject: str, html_content: str):
    """Send email notification using Resend"""
    if not resend.api_key:
        logger.warning("Resend API key not configured, skipping email")
        return None
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return None

def get_leave_approval_email(emp_name: str, leave_type: str, start_date: str, end_date: str, status: str):
    """Generate HTML email for leave approval/rejection"""
    status_color = "#10b981" if status == "approved" else "#ef4444"
    status_text = "Approved" if status == "approved" else "Rejected"
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #0b1f3b; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">BluBridge HRMS</h1>
        </div>
        <div style="background: #fffdf7; padding: 30px; border: 1px solid #e5e5e5; border-top: none; border-radius: 0 0 8px 8px;">
            <h2 style="color: #0b1f3b; margin-top: 0;">Leave Request {status_text}</h2>
            <p style="color: #666;">Dear {emp_name},</p>
            <p style="color: #666;">Your leave request has been <span style="color: {status_color}; font-weight: bold;">{status_text.lower()}</span>.</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Leave Type:</strong> {leave_type}</p>
                <p style="margin: 5px 0;"><strong>From:</strong> {start_date}</p>
                <p style="margin: 5px 0;"><strong>To:</strong> {end_date}</p>
                <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: {status_color};">{status_text}</span></p>
            </div>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">This is an automated notification from BluBridge HRMS.</p>
        </div>
    </div>
    """

def get_star_reward_email(emp_name: str, stars: int, reason: str, awarded_by: str):
    """Generate HTML email for star reward notification"""
    star_color = "#10b981" if stars > 0 else "#ef4444"
    star_text = f"+{stars}" if stars > 0 else str(stars)
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #0b1f3b; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">BluBridge HRMS</h1>
        </div>
        <div style="background: #fffdf7; padding: 30px; border: 1px solid #e5e5e5; border-top: none; border-radius: 0 0 8px 8px;">
            <h2 style="color: #0b1f3b; margin-top: 0;">Star Reward Notification</h2>
            <p style="color: #666;">Dear {emp_name},</p>
            <p style="color: #666;">You have received a star reward!</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <p style="font-size: 48px; margin: 0; color: {star_color};">{star_text} ⭐</p>
                <p style="margin: 10px 0 0 0; color: #666;">{reason}</p>
            </div>
            <p style="color: #999; font-size: 12px;">Awarded by: {awarded_by}</p>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">This is an automated notification from BluBridge HRMS.</p>
        </div>
    </div>
    """

def get_welcome_email(emp_name: str, emp_id: str, username: str, password: str, login_url: str):
    """Generate HTML email for new employee welcome with credentials"""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #0b1f3b 0%, #1e3a5f 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600;">Welcome to BluBridge!</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0; font-size: 14px;">Your Employee Account Has Been Created</p>
        </div>
        <div style="background: #fffdf7; padding: 35px; border: 1px solid #e5e5e5; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="color: #333; font-size: 16px; margin-top: 0;">Dear <strong>{emp_name}</strong>,</p>
            <p style="color: #666; line-height: 1.6;">Welcome to the BluBridge team! Your employee account has been successfully created. Below are your login credentials to access the BluBridge HRMS portal.</p>
            
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 25px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #0b1f3b;">
                <h3 style="color: #0b1f3b; margin: 0 0 15px 0; font-size: 16px;">🔐 Your Login Credentials</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 120px;">Employee ID:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600;">{emp_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">Username:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600;">{username}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">Password:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600; font-family: monospace; background: #fff; padding: 5px 10px; border-radius: 4px;">{password}</td>
                    </tr>
                </table>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{login_url}" style="display: inline-block; background: #0b1f3b; color: white; padding: 14px 35px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">Login to HRMS Portal</a>
            </div>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <p style="color: #856404; margin: 0; font-size: 13px;">⚠️ <strong>Security Reminder:</strong> Please change your password after your first login for security purposes.</p>
            </div>
            
            <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 25px 0;">
            
            <p style="color: #999; font-size: 12px; margin-bottom: 5px;">If you have any questions, please contact HR at hrms@blubridge.ai</p>
            <p style="color: #999; font-size: 12px; margin: 0;">This is an automated notification from BluBridge HRMS.</p>
        </div>
    </div>
    """

async def send_welcome_email(emp_name: str, emp_id: str, email: str, username: str, password: str, login_url: str):
    """Send welcome email with credentials to new employee"""
    resend_api_key = os.environ.get('RESEND_API_KEY')
    sender_email = os.environ.get('SENDER_EMAIL', 'hrms@blubridge.ai')
    
    if not resend_api_key:
        logger.warning("RESEND_API_KEY not configured - skipping welcome email")
        return None
    
    resend.api_key = resend_api_key
    
    html_content = get_welcome_email(emp_name, emp_id, username, password, login_url)
    
    params = {
        "from": sender_email,
        "to": [email],
        "subject": f"Welcome to BluBridge - Your Login Credentials ({emp_id})",
        "html": html_content
    }
    
    try:
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Welcome email sent to {email}")
        return email_result
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {str(e)}")
        return None

# ============== CLOUDINARY ROUTES ==============

@api_router.get("/cloudinary/signature")
async def get_cloudinary_signature(
    resource_type: str = Query("image", enum=["image", "video", "auto"]),
    folder: str = Query("employees"),
    current_user: dict = Depends(get_current_user)
):
    """Generate signed upload params for Cloudinary"""
    ALLOWED_FOLDERS = ("employees", "documents", "avatars")
    if folder not in ALLOWED_FOLDERS:
        raise HTTPException(status_code=400, detail="Invalid folder path")
    
    timestamp = int(time.time())
    # Only include params that are part of the upload request signature
    params = {
        "timestamp": timestamp,
        "folder": f"blubridge/{folder}"
    }
    
    signature = cloudinary.utils.api_sign_request(
        params,
        os.environ.get("CLOUDINARY_API_SECRET")
    )
    
    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME"),
        "api_key": os.environ.get("CLOUDINARY_API_KEY"),
        "folder": f"blubridge/{folder}",
        "resource_type": resource_type  # Returned but not signed
    }

@api_router.delete("/cloudinary/{public_id:path}")
async def delete_cloudinary_asset(
    public_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete asset from Cloudinary"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        result = await asyncio.to_thread(
            cloudinary.uploader.destroy,
            public_id,
            invalidate=True
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== AUTH ROUTES ==============

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    user = await db.users.find_one({"username": request.username}, {"_id": 0})
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled")
    
    token = create_token(user["id"], user["role"])
    await log_audit(user["id"], "login", "auth")
    
    user_response = {k: v for k, v in user.items() if k != "password_hash"}
    
    # Add onboarding info for employees
    if user.get("role") == UserRole.EMPLOYEE and user.get("employee_id"):
        onboarding = await db.onboarding.find_one({"employee_id": user["employee_id"]}, {"_id": 0})
        user_response["onboarding_status"] = onboarding.get("status") if onboarding else user.get("onboarding_status", OnboardingStatus.PENDING)
        user_response["is_first_login"] = user.get("is_first_login", True)
        user_response["onboarding_completed"] = user_response["onboarding_status"] == OnboardingStatus.APPROVED
    
    return {"token": token, "user": user_response}

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k != "password_hash"}

@api_router.put("/auth/update-profile")
async def update_admin_profile(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update admin user profile"""
    update_data = {}
    if name:
        update_data["name"] = name
    if email:
        update_data["email"] = email
    if phone:
        update_data["phone"] = phone
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    update_data["updated_at"] = get_ist_now().isoformat()
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
    
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    return serialize_doc(user)

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@api_router.post("/auth/change-password")
async def change_admin_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """Change admin user password"""
    user = await db.users.find_one({"id": current_user["id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    current_hash = hashlib.sha256(data.current_password.encode()).hexdigest()
    if user.get("password_hash") != current_hash:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Update to new password
    new_hash = hashlib.sha256(data.new_password.encode()).hexdigest()
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {
            "password_hash": new_hash,
            "updated_at": get_ist_now().isoformat()
        }}
    )
    
    return {"message": "Password changed successfully"}

# ============== EMPLOYEE MASTER ROUTES ==============

@api_router.get("/employees")
async def get_employees(
    department: Optional[str] = None,
    team: Optional[str] = None,
    status: Optional[str] = None,
    employment_type: Optional[str] = None,
    tier_level: Optional[str] = None,
    work_location: Optional[str] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    query = {}
    
    # Exclude soft-deleted by default
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
    
    if department and department != "All":
        query["department"] = department
    if team and team != "All":
        query["team"] = team
    if status and status != "All":
        query["employee_status"] = status
    if employment_type and employment_type != "All":
        query["employment_type"] = employment_type
    if tier_level and tier_level != "All":
        query["tier_level"] = tier_level
    if work_location and work_location != "All":
        query["work_location"] = work_location
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"official_email": {"$regex": search, "$options": "i"}},
            {"emp_id": {"$regex": search, "$options": "i"}},
            {"designation": {"$regex": search, "$options": "i"}}
        ]
    
    skip = (page - 1) * limit
    total = await db.employees.count_documents(query)
    employees = await db.employees.find(query, {"_id": 0}).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
    
    # Add reporting manager name
    for emp in employees:
        if emp.get("reporting_manager_id"):
            manager = await db.employees.find_one({"id": emp["reporting_manager_id"]}, {"_id": 0, "full_name": 1})
            emp["reporting_manager_name"] = manager.get("full_name") if manager else None
    
    return {
        "employees": [serialize_doc(e) for e in employees],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@api_router.get("/employees/all")
async def get_all_employees(current_user: dict = Depends(get_current_user)):
    """Get all active employees (for dropdowns)"""
    query = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
    employees = await db.employees.find(query, {"_id": 0, "id": 1, "emp_id": 1, "full_name": 1, "department": 1, "team": 1}).to_list(1000)
    return employees

@api_router.get("/employees/stats")
async def get_employee_stats(current_user: dict = Depends(get_current_user)):
    """Get employee statistics for dashboard"""
    base_query = {"is_deleted": {"$ne": True}}
    
    total = await db.employees.count_documents(base_query)
    active = await db.employees.count_documents({**base_query, "employee_status": EmployeeStatus.ACTIVE})
    inactive = await db.employees.count_documents({**base_query, "employee_status": EmployeeStatus.INACTIVE})
    resigned = await db.employees.count_documents({**base_query, "employee_status": EmployeeStatus.RESIGNED})
    
    # By department
    by_department = {}
    departments = await db.departments.find({}, {"_id": 0, "name": 1}).to_list(100)
    for dept in departments:
        count = await db.employees.count_documents({**base_query, "department": dept["name"], "employee_status": EmployeeStatus.ACTIVE})
        by_department[dept["name"]] = count
    
    # By employment type
    by_type = {}
    for emp_type in [EmploymentType.FULL_TIME, EmploymentType.PART_TIME, EmploymentType.CONTRACT, EmploymentType.INTERN]:
        count = await db.employees.count_documents({**base_query, "employment_type": emp_type, "employee_status": EmployeeStatus.ACTIVE})
        by_type[emp_type] = count
    
    # By work location
    by_location = {}
    for loc in [WorkLocation.REMOTE, WorkLocation.OFFICE, WorkLocation.HYBRID]:
        count = await db.employees.count_documents({**base_query, "work_location": loc, "employee_status": EmployeeStatus.ACTIVE})
        by_location[loc] = count
    
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "resigned": resigned,
        "by_department": by_department,
        "by_employment_type": by_type,
        "by_work_location": by_location
    }

@api_router.get("/employees/{employee_id}")
async def get_employee(employee_id: str, current_user: dict = Depends(get_current_user)):
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Add reporting manager details
    if employee.get("reporting_manager_id"):
        manager = await db.employees.find_one({"id": employee["reporting_manager_id"]}, {"_id": 0, "full_name": 1, "emp_id": 1})
        employee["reporting_manager_name"] = manager.get("full_name") if manager else None
        employee["reporting_manager_emp_id"] = manager.get("emp_id") if manager else None
    
    return serialize_doc(employee)

@api_router.post("/employees")
async def create_employee(data: EmployeeCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Check for duplicate email among active employees
    existing_active = await db.employees.find_one({"official_email": data.official_email, "is_deleted": {"$ne": True}})
    if existing_active:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")
    
    # Check if there's a deleted employee with same email - reactivate instead
    existing_deleted = await db.employees.find_one({"official_email": data.official_email, "is_deleted": True})
    
    username = data.official_email.split('@')[0]
    name_part = data.full_name.replace(' ', '').lower()[:4]
    if data.phone_number and len(data.phone_number) >= 4:
        phone_part = data.phone_number[-4:]
    else:
        phone_part = str(uuid.uuid4())[:4]
    temp_password = f"{name_part}@{phone_part}"
    
    frontend_url = os.environ.get('FRONTEND_URL', 'https://hrms-biometric.preview.emergentagent.com')
    login_url = f"{frontend_url}/login"
    
    if existing_deleted:
        # Reactivate the deleted employee with updated info
        emp_id = existing_deleted.get("emp_id")
        employee_id = existing_deleted.get("id")
        
        update_data = {
            "is_deleted": False,
            "deleted_at": None,
            "employee_status": EmployeeStatus.ACTIVE,
            "full_name": data.full_name,
            "phone_number": data.phone_number,
            "gender": data.gender,
            "date_of_birth": data.date_of_birth,
            "date_of_joining": data.date_of_joining,
            "employment_type": data.employment_type,
            "designation": data.designation,
            "tier_level": data.tier_level,
            "reporting_manager_id": data.reporting_manager_id,
            "department": data.department,
            "team": data.team,
            "work_location": data.work_location,
            "leave_policy": data.leave_policy,
            "shift_type": data.shift_type,
            "attendance_tracking_enabled": data.attendance_tracking_enabled,
            "user_role": data.user_role,
            "login_enabled": data.login_enabled,
            "updated_at": get_ist_now().isoformat()
        }
        
        await db.employees.update_one({"id": employee_id}, {"$set": update_data})
        
        # Update team member count
        await db.teams.update_one({"name": data.team}, {"$inc": {"member_count": 1}})
        
        # Update or create user account with new credentials
        if data.login_enabled:
            existing_user = await db.users.find_one({"username": username})
            if existing_user:
                # Update existing user with new password and reactivate
                await db.users.update_one(
                    {"username": username},
                    {"$set": {
                        "password_hash": hash_password(temp_password),
                        "is_active": True,
                        "name": data.full_name,
                        "role": data.user_role if data.user_role else UserRole.EMPLOYEE,
                        "department": data.department,
                        "team": data.team
                    }}
                )
            else:
                # Create new user
                new_user = User(
                    username=username,
                    email=data.official_email,
                    password_hash=hash_password(temp_password),
                    name=data.full_name,
                    role=data.user_role if data.user_role else UserRole.EMPLOYEE,
                    employee_id=employee_id,
                    department=data.department,
                    team=data.team
                )
                user_doc = new_user.model_dump()
                user_doc['created_at'] = user_doc['created_at'].isoformat()
                await db.users.insert_one(user_doc.copy())
            
            # Send welcome email with new credentials
            asyncio.create_task(
                send_welcome_email(
                    emp_name=data.full_name,
                    emp_id=emp_id,
                    email=data.official_email,
                    username=username,
                    password=temp_password,
                    login_url=login_url
                )
            )
        
        await log_audit(current_user["id"], "reactivate", "employee", employee_id, f"Reactivated employee: {data.full_name}")
        
        employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
        result = serialize_doc(employee)
        if data.login_enabled:
            result['temp_password'] = temp_password
            result['username'] = username
            result['reactivated'] = True
        
        return result
    
    # Create new employee
    emp_id = await generate_emp_id()
    
    employee = Employee(
        emp_id=emp_id,
        full_name=data.full_name,
        official_email=data.official_email,
        phone_number=data.phone_number,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        date_of_joining=data.date_of_joining,
        employment_type=data.employment_type,
        designation=data.designation,
        tier_level=data.tier_level,
        reporting_manager_id=data.reporting_manager_id,
        department=data.department,
        team=data.team,
        work_location=data.work_location,
        leave_policy=data.leave_policy,
        shift_type=data.shift_type,
        attendance_tracking_enabled=data.attendance_tracking_enabled,
        user_role=data.user_role,
        login_enabled=data.login_enabled
    )
    
    doc = employee.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.employees.insert_one(doc.copy())
    
    # Update team member count
    await db.teams.update_one({"name": data.team}, {"$inc": {"member_count": 1}})
    
    # Create user account if login is enabled
    if data.login_enabled:
        # Check if user already exists (unlikely for new employee, but check anyway)
        existing_user = await db.users.find_one({"username": username})
        if not existing_user:
            new_user = User(
                username=username,
                email=data.official_email,
                password_hash=hash_password(temp_password),
                name=data.full_name,
                role=data.user_role if data.user_role else UserRole.EMPLOYEE,
                employee_id=employee.id,
                department=data.department,
                team=data.team
            )
            user_doc = new_user.model_dump()
            user_doc['created_at'] = user_doc['created_at'].isoformat()
            await db.users.insert_one(user_doc.copy())
        
        # Send welcome email with credentials
        asyncio.create_task(
            send_welcome_email(
                emp_name=data.full_name,
                emp_id=emp_id,
                email=data.official_email,
                username=username,
                password=temp_password,
                login_url=login_url
            )
        )
    
    await log_audit(current_user["id"], "create", "employee", employee.id, f"Created employee: {data.full_name}")
    
    # Create onboarding record for new employee
    onboarding_record = OnboardingRecord(
        employee_id=employee.id,
        emp_id=emp_id,
        emp_name=data.full_name,
        department=data.department,
        team=data.team,
        designation=data.designation
    )
    onboarding_doc = onboarding_record.model_dump()
    onboarding_doc['created_at'] = onboarding_doc['created_at'].isoformat()
    onboarding_doc['updated_at'] = onboarding_doc['updated_at'].isoformat()
    await db.onboarding.insert_one(onboarding_doc.copy())
    
    # Create document placeholders for onboarding
    for req_doc in REQUIRED_DOCUMENTS:
        doc_record = OnboardingDocument(
            employee_id=employee.id,
            document_type=req_doc["type"],
            document_label=req_doc["label"]
        )
        doc_data = doc_record.model_dump()
        doc_data['created_at'] = doc_data['created_at'].isoformat()
        await db.onboarding_documents.insert_one(doc_data.copy())
    
    result = serialize_doc(doc)
    if data.login_enabled:
        result['temp_password'] = temp_password
        result['username'] = username
    
    return result

@api_router.put("/employees/{employee_id}")
async def update_employee(employee_id: str, data: EmployeeUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    existing = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check for duplicate email if changing
    if data.official_email and data.official_email != existing.get("official_email"):
        dup = await db.employees.find_one({"official_email": data.official_email, "id": {"$ne": employee_id}, "is_deleted": {"$ne": True}})
        if dup:
            raise HTTPException(status_code=400, detail="Employee with this email already exists")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    update_data["updated_at"] = get_ist_now().isoformat()
    
    # Handle team change
    old_team = existing.get("team")
    new_team = update_data.get("team")
    if new_team and old_team and new_team != old_team:
        await db.teams.update_one({"name": old_team}, {"$inc": {"member_count": -1}})
        await db.teams.update_one({"name": new_team}, {"$inc": {"member_count": 1}})
    
    result = await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    await log_audit(current_user["id"], "update", "employee", employee_id, f"Updated fields: {list(update_data.keys())}")
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return serialize_doc(employee)

@api_router.delete("/employees/{employee_id}")
async def deactivate_employee(employee_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete - deactivates employee"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    existing = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = {
        "is_deleted": True,
        "deleted_at": get_ist_now().isoformat(),
        "employee_status": EmployeeStatus.INACTIVE,
        "login_enabled": False,
        "updated_at": get_ist_now().isoformat()
    }
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    
    # Update team member count
    await db.teams.update_one({"name": existing.get("team")}, {"$inc": {"member_count": -1}})
    
    # Deactivate the user account as well
    username = existing.get("official_email", "").split('@')[0]
    if username:
        await db.users.update_one(
            {"username": username},
            {"$set": {"is_active": False}}
        )
    
    await log_audit(current_user["id"], "deactivate", "employee", employee_id, f"Deactivated employee: {existing.get('full_name')}")
    return {"message": "Employee deactivated successfully"}

@api_router.put("/employees/{employee_id}/restore")
async def restore_employee(employee_id: str, current_user: dict = Depends(get_current_user)):
    """Restore soft-deleted employee"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    existing = await db.employees.find_one({"id": employee_id, "is_deleted": True}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Deleted employee not found")
    
    update_data = {
        "is_deleted": False,
        "deleted_at": None,
        "employee_status": EmployeeStatus.ACTIVE,
        "updated_at": get_ist_now().isoformat()
    }
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    
    # Update team member count
    await db.teams.update_one({"name": existing.get("team")}, {"$inc": {"member_count": 1}})
    
    await log_audit(current_user["id"], "restore", "employee", employee_id, f"Restored employee: {existing.get('full_name')}")
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return serialize_doc(employee)

class AvatarUpdate(BaseModel):
    avatar_url: str
    avatar_public_id: Optional[str] = None

@api_router.put("/employees/{employee_id}/avatar")
async def update_employee_avatar(employee_id: str, data: AvatarUpdate, current_user: dict = Depends(get_current_user)):
    """Update employee avatar/photo"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    existing = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Delete old avatar from Cloudinary if exists
    old_public_id = existing.get("avatar_public_id")
    if old_public_id:
        try:
            await asyncio.to_thread(cloudinary.uploader.destroy, old_public_id, invalidate=True)
        except Exception as e:
            logger.warning(f"Failed to delete old avatar: {e}")
    
    await db.employees.update_one(
        {"id": employee_id},
        {"$set": {
            "avatar": data.avatar_url,
            "avatar_public_id": data.avatar_public_id,
            "updated_at": get_ist_now().isoformat()
        }}
    )
    
    await log_audit(current_user["id"], "update_avatar", "employee", employee_id)
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return serialize_doc(employee)

# ============== ATTENDANCE ROUTES ==============

@api_router.get("/attendance")
async def get_attendance(
    employee_name: Optional[str] = None,
    team: Optional[str] = None,
    department: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if employee_name:
        query["emp_name"] = {"$regex": employee_name, "$options": "i"}
    if team and team != "All":
        query["team"] = team
    if department and department != "All":
        query["department"] = department
    if from_date:
        query["date"] = {"$gte": from_date}
    if to_date:
        if "date" in query:
            query["date"]["$lte"] = to_date
        else:
            query["date"] = {"$lte": to_date}
    if status and status != "All":
        query["status"] = status
    
    attendance = await db.attendance.find(query, {"_id": 0}).sort("date", -1).to_list(1000)
    return [serialize_doc(a) for a in attendance]

@api_router.post("/attendance/check-in")
async def check_in(employee_id: str, current_user: dict = Depends(get_current_user)):
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if not employee.get("attendance_tracking_enabled", True):
        raise HTTPException(status_code=400, detail="Attendance tracking disabled for this employee")
    
    today = get_ist_today()
    existing = await db.attendance.find_one({"employee_id": employee_id, "date": today})
    
    if existing and existing.get("check_in"):
        raise HTTPException(status_code=400, detail="Already checked in today")
    
    now = get_ist_now()
    check_in_time = now.strftime("%I:%M %p")
    check_in_24h = now.strftime("%H:%M")
    
    # Get shift timings for the employee
    shift_timings = get_shift_timings(employee)
    expected_login = shift_timings.get("login_time") if shift_timings else None
    expected_logout = shift_timings.get("logout_time") if shift_timings else None
    
    # Initial status calculation (will be finalized on check-out)
    initial_status = AttendanceStatus.LOGIN
    is_lop = False
    lop_reason = None
    
    # For fixed shifts, check if late login
    if expected_login:
        expected_mins = parse_time_24h_to_minutes(expected_login)
        actual_mins = parse_time_24h_to_minutes(check_in_24h)
        
        if actual_mins > expected_mins:
            late_mins = actual_mins - expected_mins
            initial_status = AttendanceStatus.LOSS_OF_PAY
            is_lop = True
            lop_reason = f"Late login by {late_mins} minute(s). Expected: {expected_login}, Actual: {check_in_24h}"
    
    attendance = Attendance(
        employee_id=employee_id,
        emp_name=employee["full_name"],
        team=employee["team"],
        department=employee["department"],
        date=today,
        check_in=check_in_time,
        check_in_24h=check_in_24h,
        status=initial_status,
        is_lop=is_lop,
        lop_reason=lop_reason,
        shift_type=employee.get("shift_type", "General"),
        expected_login=expected_login,
        expected_logout=expected_logout
    )
    doc = attendance.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.attendance.insert_one(doc.copy())
    
    return serialize_doc(doc)

@api_router.post("/attendance/check-out")
async def check_out(employee_id: str, current_user: dict = Depends(get_current_user)):
    today = get_ist_today()
    attendance = await db.attendance.find_one({"employee_id": employee_id, "date": today}, {"_id": 0})
    
    if not attendance:
        raise HTTPException(status_code=404, detail="No check-in found for today")
    if attendance.get("check_out"):
        raise HTTPException(status_code=400, detail="Already checked out")
    
    # Get employee for shift info
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    shift_timings = get_shift_timings(employee) if employee else None
    
    now = get_ist_now()
    check_out_time = now.strftime("%I:%M %p")
    check_out_24h = now.strftime("%H:%M")
    
    check_in_24h = attendance.get("check_in_24h")
    if not check_in_24h and attendance.get("check_in"):
        check_in_24h = parse_time_12h_to_24h(attendance.get("check_in"))
    
    # Calculate attendance status with strict LOP rules
    if shift_timings:
        status_result = calculate_attendance_status(check_in_24h, check_out_24h, shift_timings)
    else:
        # No shift timings - just mark as completed
        status_result = {
            "status": AttendanceStatus.COMPLETED,
            "is_lop": False,
            "lop_reason": None,
            "total_hours_decimal": 0.0
        }
        # Calculate hours manually
        if check_in_24h:
            in_mins = parse_time_24h_to_minutes(check_in_24h)
            out_mins = parse_time_24h_to_minutes(check_out_24h)
            if out_mins < in_mins:
                total_mins = 24 * 60 - in_mins + out_mins
            else:
                total_mins = out_mins - in_mins
            status_result["total_hours_decimal"] = total_mins / 60
    
    total_hours_str = calculate_total_hours_str(status_result.get("total_hours_decimal", 0))
    
    # If already marked as LOP from late login, keep it
    final_is_lop = attendance.get("is_lop", False) or status_result.get("is_lop", False)
    final_lop_reason = attendance.get("lop_reason") or status_result.get("lop_reason")
    final_status = AttendanceStatus.LOSS_OF_PAY if final_is_lop else status_result.get("status", AttendanceStatus.COMPLETED)
    
    update_data = {
        "check_out": check_out_time,
        "check_out_24h": check_out_24h,
        "total_hours": total_hours_str,
        "total_hours_decimal": status_result.get("total_hours_decimal", 0),
        "status": final_status,
        "is_lop": final_is_lop,
        "lop_reason": final_lop_reason
    }
    
    await db.attendance.update_one(
        {"employee_id": employee_id, "date": today},
        {"$set": update_data}
    )
    
    updated = await db.attendance.find_one({"employee_id": employee_id, "date": today}, {"_id": 0})
    return serialize_doc(updated)

@api_router.get("/attendance/stats")
async def get_attendance_stats(
    date: Optional[str] = None, 
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Use single date or date range
    if not date and not from_date:
        date = get_ist_today()
    
    # Only count active employees with attendance tracking enabled
    total_employees = await db.employees.count_documents({
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": {"$ne": True},
        "attendance_tracking_enabled": True
    })
    
    # Build date query
    if from_date and to_date:
        date_query = {"date": {"$gte": from_date, "$lte": to_date}}
    else:
        date_query = {"date": date}
    
    # Count all logged in (including Late Login, Early Out, Present, Loss of Pay since they also logged in)
    logged_in = await db.attendance.count_documents({
        **date_query, 
        "status": {"$in": ["Login", "Completed", "Late Login", "Early Out", "Present", "Loss of Pay"]}
    })
    not_logged = total_employees - logged_in
    
    # Count early out (can overlap with late login)
    early_out = await db.attendance.count_documents({**date_query, "status": "Early Out"})
    
    # Count late login (can overlap with early out)
    late_login = await db.attendance.count_documents({**date_query, "status": "Late Login"})
    
    # Count Loss of Pay
    lop_count = await db.attendance.count_documents({**date_query, "is_lop": True})
    
    # Count completed (logged out)
    logout = await db.attendance.count_documents({
        **date_query, 
        "status": {"$in": ["Completed", "Early Out", "Present", "Loss of Pay"]}
    })
    
    # Count present (no LOP)
    present = await db.attendance.count_documents({
        **date_query, 
        "status": {"$in": ["Present", "Completed"]},
        "is_lop": {"$ne": True}
    })
    
    return {
        "total_employees": total_employees,
        "logged_in": logged_in,
        "not_logged": max(0, not_logged),
        "early_out": early_out,
        "late_login": late_login,
        "logout": logout,
        "lop_count": lop_count,
        "present": present
    }

# ============== LEAVE ROUTES ==============

@api_router.get("/leaves")
async def get_leaves(
    employee_name: Optional[str] = None,
    team: Optional[str] = None,
    department: Optional[str] = None,
    leave_type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if employee_name:
        query["emp_name"] = {"$regex": employee_name, "$options": "i"}
    if team and team != "All":
        query["team"] = team
    if department and department != "All":
        query["department"] = department
    if leave_type and leave_type != "All":
        query["leave_type"] = leave_type
    if status and status != "All":
        query["status"] = status
    if from_date:
        query["start_date"] = {"$gte": from_date}
    if to_date:
        if "start_date" in query:
            query["start_date"]["$lte"] = to_date
        else:
            query["start_date"] = {"$lte": to_date}
    
    leaves = await db.leaves.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [serialize_doc(l) for l in leaves]

@api_router.post("/leaves")
async def create_leave(data: LeaveRequestCreate, current_user: dict = Depends(get_current_user)):
    employee = await db.employees.find_one({"id": data.employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    start = datetime.strptime(data.start_date, "%Y-%m-%d")
    end = datetime.strptime(data.end_date, "%Y-%m-%d")
    duration = (end - start).days + 1
    
    leave = LeaveRequest(
        employee_id=data.employee_id,
        emp_name=employee["full_name"],
        team=employee["team"],
        department=employee["department"],
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        duration=f"{duration} day(s)",
        reason=data.reason
    )
    doc = leave.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.leaves.insert_one(doc.copy())
    
    await log_audit(current_user["id"], "create", "leave", leave.id)
    return serialize_doc(doc)

@api_router.put("/leaves/{leave_id}/approve")
async def approve_leave(leave_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.TEAM_LEAD]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    leave = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    result = await db.leaves.update_one(
        {"id": leave_id},
        {"$set": {"status": "approved", "approved_by": current_user["id"], "approved_at": get_ist_now().isoformat()}}
    )
    
    await log_audit(current_user["id"], "approve", "leave", leave_id)
    
    # Send email notification
    employee = await db.employees.find_one({"id": leave["employee_id"]}, {"_id": 0})
    if employee and employee.get("official_email"):
        email_html = get_leave_approval_email(
            employee["full_name"],
            leave["leave_type"],
            leave["start_date"],
            leave["end_date"],
            "approved"
        )
        asyncio.create_task(send_email_notification(
            employee["official_email"],
            "Leave Request Approved - BluBridge HRMS",
            email_html
        ))
    leave = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    return serialize_doc(leave)

@api_router.put("/leaves/{leave_id}/reject")
async def reject_leave(leave_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.TEAM_LEAD]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    leave = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    result = await db.leaves.update_one(
        {"id": leave_id},
        {"$set": {"status": "rejected", "approved_by": current_user["id"], "approved_at": get_ist_now().isoformat()}}
    )
    
    await log_audit(current_user["id"], "reject", "leave", leave_id)
    
    # Send email notification
    employee = await db.employees.find_one({"id": leave["employee_id"]}, {"_id": 0})
    if employee and employee.get("official_email"):
        email_html = get_leave_approval_email(
            employee["full_name"],
            leave["leave_type"],
            leave["start_date"],
            leave["end_date"],
            "rejected"
        )
        asyncio.create_task(send_email_notification(
            employee["official_email"],
            "Leave Request Rejected - BluBridge HRMS",
            email_html
        ))
    
    leave = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    return serialize_doc(leave)

# ============== STAR REWARDS ROUTES ==============

@api_router.get("/star-rewards")
async def get_star_rewards(
    team: Optional[str] = None,
    department: Optional[str] = None,
    month: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
    if team and team != "All":
        query["team"] = team
    if department and department != "All":
        query["department"] = department
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"official_email": {"$regex": search, "$options": "i"}},
            {"emp_id": {"$regex": search, "$options": "i"}}
        ]
    
    employees = await db.employees.find(query, {"_id": 0}).to_list(1000)
    
    # Map full_name to name for backward compatibility
    for emp in employees:
        emp["name"] = emp.get("full_name", "")
        emp["email"] = emp.get("official_email", "")
    
    return [serialize_doc(e) for e in employees]

@api_router.post("/star-rewards")
async def add_star_reward(data: StarRewardCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.TEAM_LEAD]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    employee = await db.employees.find_one({"id": data.employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Restrict to Research Unit employees only
    if employee.get("department") != "Research Unit":
        raise HTTPException(status_code=400, detail="Star rewards can only be given to Research Unit employees")
    
    current_month = get_ist_now().strftime("%Y-%m")
    
    reward = StarReward(
        employee_id=data.employee_id,
        stars=data.stars,
        reason=data.reason,
        type=data.type,
        awarded_by=current_user["id"],
        month=current_month
    )
    doc = reward.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.star_rewards.insert_one(doc.copy())
    
    # Update employee stars and unsafe count
    new_stars = employee.get("stars", 0) + data.stars
    update_data = {"stars": new_stars}
    
    # If type is unsafe, increment unsafe count
    if data.type == "unsafe":
        new_unsafe = employee.get("unsafe_count", 0) + 1
        update_data["unsafe_count"] = new_unsafe
    
    await db.employees.update_one({"id": data.employee_id}, {"$set": update_data})
    
    await log_audit(current_user["id"], "award_stars", "star_reward", reward.id)
    
    # Send email notification
    if employee.get("official_email"):
        awarder = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
        awarder_name = awarder.get("name", "Admin") if awarder else "Admin"
        email_html = get_star_reward_email(
            employee["full_name"],
            data.stars,
            data.reason,
            awarder_name
        )
        asyncio.create_task(send_email_notification(
            employee["official_email"],
            "Star Reward Notification - BluBridge HRMS",
            email_html
        ))
    
    return {"message": "Stars awarded", "new_total": new_stars}

@api_router.get("/star-rewards/history/{employee_id}")
async def get_star_history(employee_id: str, current_user: dict = Depends(get_current_user)):
    rewards = await db.star_rewards.find({"employee_id": employee_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [serialize_doc(r) for r in rewards]

# ============== TEAM ROUTES ==============

@api_router.get("/teams")
async def get_teams(department: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if department and department != "All":
        query["department"] = department
    
    teams = await db.teams.find(query, {"_id": 0}).to_list(100)
    
    # Calculate actual member count from employees
    for team in teams:
        count = await db.employees.count_documents({
            "team": team["name"],
            "is_deleted": {"$ne": True},
            "employee_status": EmployeeStatus.ACTIVE
        })
        team["member_count"] = count
    
    return [serialize_doc(t) for t in teams]

@api_router.get("/teams/{team_id}")
async def get_team(team_id: str, current_user: dict = Depends(get_current_user)):
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    members = await db.employees.find({
        "team": team["name"],
        "is_deleted": {"$ne": True},
        "employee_status": EmployeeStatus.ACTIVE
    }, {"_id": 0}).to_list(100)
    
    return {"team": serialize_doc(team), "members": [serialize_doc(m) for m in members]}

@api_router.get("/departments")
async def get_departments(current_user: dict = Depends(get_current_user)):
    departments = await db.departments.find({}, {"_id": 0}).to_list(100)
    
    # Calculate actual counts
    for dept in departments:
        emp_count = await db.employees.count_documents({
            "department": dept["name"],
            "is_deleted": {"$ne": True},
            "employee_status": EmployeeStatus.ACTIVE
        })
        team_count = await db.teams.count_documents({"department": dept["name"]})
        dept["employee_count"] = emp_count
        dept["team_count"] = team_count
    
    return [serialize_doc(d) for d in departments]

# ============== DASHBOARD ROUTES ==============

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    today = get_ist_now().strftime("%d-%m-%Y")
    
    # Use provided dates or default to today
    query_from = from_date if from_date else today
    query_to = to_date if to_date else today
    
    # Get counts from employee master
    base_query = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
    
    total_research = await db.employees.count_documents({**base_query, "department": "Research Unit"})
    total_support = await db.employees.count_documents({**base_query, "department": "Support Staff"})
    pending_approvals = await db.leaves.count_documents({"status": "pending"})
    upcoming_leaves = await db.leaves.count_documents({
        "status": "approved",
        "start_date": {"$gte": get_ist_now().strftime("%Y-%m-%d")}
    })
    
    # Get attendance stats with date range support
    attendance_stats = await get_attendance_stats(
        date=None, 
        from_date=query_from, 
        to_date=query_to, 
        current_user=current_user
    )
    employee_stats = await get_employee_stats(current_user)
    
    return {
        "total_research_unit": total_research,
        "total_support_staff": total_support,
        "pending_approvals": pending_approvals,
        "upcoming_leaves": upcoming_leaves,
        "attendance": attendance_stats,
        "employee_stats": employee_stats
    }

@api_router.get("/dashboard/leave-list")
async def get_dashboard_leave_list(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    today = get_ist_now().strftime("%d-%m-%Y")
    query_date = from_date if from_date else today
    
    # Get employees not logged in on the specified date
    all_employees = await db.employees.find({
        "employee_status": EmployeeStatus.ACTIVE,
        "is_deleted": {"$ne": True},
        "attendance_tracking_enabled": True
    }, {"_id": 0}).to_list(1000)
    
    # Build date query for attendance
    if from_date and to_date:
        logged_records = await db.attendance.find(
            {"date": {"$gte": from_date, "$lte": to_date}}, 
            {"_id": 0}
        ).to_list(10000)
    else:
        logged_records = await db.attendance.find({"date": query_date}, {"_id": 0}).to_list(1000)
    
    logged_ids = {a["employee_id"] for a in logged_records}
    
    not_logged = [e for e in all_employees if e["id"] not in logged_ids]
    
    result = []
    for emp in not_logged[:20]:  # Increased limit
        result.append({
            "emp_name": emp["full_name"],
            "team": emp["team"],
            "department": emp["department"],
            "leave_type": "-",
            "date": query_date,
            "status": "Not Login"
        })
    
    return result

# ============== REPORTS ROUTES ==============

@api_router.get("/reports/attendance")
async def get_attendance_report(
    from_date: str,
    to_date: str,
    department: Optional[str] = None,
    team: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"date": {"$gte": from_date, "$lte": to_date}}
    if team and team != "All":
        query["team"] = team
    if department and department != "All":
        query["department"] = department
    
    records = await db.attendance.find(query, {"_id": 0}).to_list(10000)
    return [serialize_doc(r) for r in records]

@api_router.get("/reports/leaves")
async def get_leave_report(
    from_date: str,
    to_date: str,
    department: Optional[str] = None,
    team: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"start_date": {"$gte": from_date, "$lte": to_date}}
    if team and team != "All":
        query["team"] = team
    if department and department != "All":
        query["department"] = department
    
    records = await db.leaves.find(query, {"_id": 0}).to_list(10000)
    return [serialize_doc(r) for r in records]

@api_router.get("/reports/employees")
async def get_employee_report(
    department: Optional[str] = None,
    team: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {"is_deleted": {"$ne": True}}
    if department and department != "All":
        query["department"] = department
    if team and team != "All":
        query["team"] = team
    if status and status != "All":
        query["employee_status"] = status
    
    records = await db.employees.find(query, {"_id": 0}).to_list(10000)
    return [serialize_doc(r) for r in records]

# ============== PAYROLL ROUTES ==============

@api_router.get("/payroll")
async def get_payroll_data(
    month: str,  # Format: "YYYY-MM"
    department: Optional[str] = None,
    team: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get payroll data for all employees for a given month"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    query = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
    if department and department != "All":
        query["department"] = department
    if team and team != "All":
        query["team"] = team
    
    employees = await db.employees.find(query, {"_id": 0}).to_list(1000)
    
    payroll_data = []
    for emp in employees:
        payroll = await calculate_payroll_for_employee(emp["id"], month)
        if payroll:
            payroll_data.append(payroll)
    
    return payroll_data

@api_router.get("/payroll/{employee_id}")
async def get_employee_payroll(
    employee_id: str,
    month: str,  # Format: "YYYY-MM"
    current_user: dict = Depends(get_current_user)
):
    """Get detailed payroll for a specific employee"""
    payroll = await calculate_payroll_for_employee(employee_id, month)
    if not payroll:
        raise HTTPException(status_code=404, detail="Employee not found")
    return payroll

@api_router.get("/payroll/summary/{month}")
async def get_payroll_summary(
    month: str,  # Format: "YYYY-MM"
    department: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get payroll summary for a month"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    query = {"is_deleted": {"$ne": True}, "employee_status": EmployeeStatus.ACTIVE}
    if department and department != "All":
        query["department"] = department
    
    employees = await db.employees.find(query, {"_id": 0}).to_list(1000)
    
    total_employees = len(employees)
    total_salary = 0.0
    total_deductions = 0.0
    total_net_salary = 0.0
    total_lop_days = 0
    total_present_days = 0
    
    for emp in employees:
        payroll = await calculate_payroll_for_employee(emp["id"], month)
        if payroll:
            total_salary += payroll.get("monthly_salary", 0)
            total_deductions += payroll.get("lop_deduction", 0)
            total_net_salary += payroll.get("net_salary", 0)
            total_lop_days += payroll.get("lop_days", 0)
            total_present_days += payroll.get("present_days", 0)
    
    return {
        "month": month,
        "total_employees": total_employees,
        "total_salary": round(total_salary, 2),
        "total_deductions": round(total_deductions, 2),
        "total_net_salary": round(total_net_salary, 2),
        "total_lop_days": total_lop_days,
        "total_present_days": total_present_days
    }

# ============== SHIFT CONFIGURATION ROUTES ==============

@api_router.get("/config/shifts")
async def get_shift_configurations(current_user: dict = Depends(get_current_user)):
    """Get all available shift configurations"""
    shifts = []
    for shift_type, config in SHIFT_DEFINITIONS.items():
        shifts.append({
            "type": shift_type,
            "login_time": config.get("login_time"),
            "logout_time": config.get("logout_time"),
            "total_hours": config.get("total_hours"),
            "description": config.get("description")
        })
    return shifts

@api_router.get("/config/shift/{shift_type}")
async def get_shift_details(shift_type: str, current_user: dict = Depends(get_current_user)):
    """Get details for a specific shift type"""
    if shift_type not in SHIFT_DEFINITIONS:
        raise HTTPException(status_code=404, detail="Shift type not found")
    
    config = SHIFT_DEFINITIONS[shift_type]
    return {
        "type": shift_type,
        "login_time": config.get("login_time"),
        "logout_time": config.get("logout_time"),
        "total_hours": config.get("total_hours"),
        "description": config.get("description")
    }

@api_router.put("/employees/{employee_id}/shift")
async def update_employee_shift(
    employee_id: str,
    shift_data: ShiftConfigCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update employee's shift configuration"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = {"shift_type": shift_data.shift_type}
    
    if shift_data.shift_type == "Custom":
        if not shift_data.login_time or not shift_data.logout_time:
            raise HTTPException(status_code=400, detail="Custom shift requires login_time and logout_time")
        
        update_data["custom_login_time"] = shift_data.login_time
        update_data["custom_logout_time"] = shift_data.logout_time
        
        # Calculate total hours
        login_mins = parse_time_24h_to_minutes(shift_data.login_time)
        logout_mins = parse_time_24h_to_minutes(shift_data.logout_time)
        
        if logout_mins < login_mins:
            total_hours = (24 * 60 - login_mins + logout_mins) / 60
        else:
            total_hours = (logout_mins - login_mins) / 60
        
        update_data["custom_total_hours"] = total_hours
    else:
        # Clear custom fields for predefined shifts
        update_data["custom_login_time"] = None
        update_data["custom_logout_time"] = None
        update_data["custom_total_hours"] = None
    
    update_data["updated_at"] = get_ist_now().isoformat()
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    
    await log_audit(current_user["id"], "update_shift", "employee", employee_id, f"Updated shift to: {shift_data.shift_type}")
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return serialize_doc(employee)

@api_router.put("/employees/{employee_id}/salary")
async def update_employee_salary(
    employee_id: str,
    monthly_salary: float = Query(..., ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Update employee's monthly salary"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = {
        "monthly_salary": monthly_salary,
        "updated_at": get_ist_now().isoformat()
    }
    
    await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    
    await log_audit(current_user["id"], "update_salary", "employee", employee_id, f"Updated salary to: {monthly_salary}")
    
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    return serialize_doc(employee)

# ============== AUDIT LOGS ==============

@api_router.get("/audit-logs")
async def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    query = {}
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    if resource:
        query["resource"] = resource
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)
    return [serialize_doc(l) for l in logs]

# ============== CONFIG/LOOKUP ROUTES ==============

@api_router.get("/config/employment-types")
async def get_employment_types():
    return [EmploymentType.FULL_TIME, EmploymentType.PART_TIME, EmploymentType.CONTRACT, EmploymentType.INTERN]

@api_router.get("/config/employee-statuses")
async def get_employee_statuses():
    return [EmployeeStatus.ACTIVE, EmployeeStatus.INACTIVE, EmployeeStatus.RESIGNED]

@api_router.get("/config/tier-levels")
async def get_tier_levels():
    return [TierLevel.JUNIOR, TierLevel.MID, TierLevel.SENIOR, TierLevel.LEAD]

@api_router.get("/config/work-locations")
async def get_work_locations():
    return [WorkLocation.REMOTE, WorkLocation.OFFICE, WorkLocation.HYBRID]

@api_router.get("/config/user-roles")
async def get_user_roles():
    return [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER, UserRole.TEAM_LEAD, UserRole.EMPLOYEE]

# ============== EMPLOYEE PORTAL MODELS ==============

class EmployeeLeaveCreate(BaseModel):
    leave_type: str  # Sick, Emergency, Preplanned
    leave_date: str  # dd-mm-yyyy
    duration: str  # First Half, Second Half, Full Day
    reason: str
    supporting_document_url: Optional[str] = None
    supporting_document_name: Optional[str] = None

class EmployeeAttendanceRecord(BaseModel):
    date: str
    login: Optional[str] = None
    logout: Optional[str] = None
    total_hours: Optional[str] = None
    status: str  # Present, Late, Early Out, Absent, Leave, NA, Sunday

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

# ============== EMPLOYEE PORTAL ROUTES ==============

@api_router.post("/employee/change-password")
async def change_employee_password(data: PasswordChangeRequest, current_user: dict = Depends(get_current_user)):
    """Change employee's own password"""
    # Validate new password matches confirmation
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    
    # Validate new password length
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
    
    # Verify current password
    current_hash = hash_password(data.current_password)
    if current_user.get("password_hash") != current_hash:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Update password in database
    new_hash = hash_password(data.new_password)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    # Log the action
    await log_audit(current_user["id"], "change_password", "user", current_user["id"])
    
    return {"message": "Password changed successfully"}

@api_router.get("/employee/profile")
async def get_employee_profile(current_user: dict = Depends(get_current_user)):
    """Get logged-in employee's profile"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee = await db.employees.find_one({"id": current_user["employee_id"], "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    
    return serialize_doc(employee)

@api_router.get("/employee/dashboard")
async def get_employee_dashboard(current_user: dict = Depends(get_current_user)):
    """Get employee dashboard data with summary cards and clock info"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Get current month attendance stats (in IST)
    now = get_ist_now()
    current_month = now.strftime("%m-%Y")
    today_str = now.strftime("%d-%m-%Y")
    
    # Calculate month boundaries
    first_day = now.replace(day=1)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    last_day = next_month - timedelta(days=1)
    
    # Get all attendance records for this month
    attendance_records = await db.attendance.find({
        "employee_id": employee_id,
        "date": {"$regex": f"-{now.strftime('%m-%Y')}$"}
    }, {"_id": 0}).to_list(31)
    
    # Calculate summary stats
    # According to requirements: if "Early Out" has late login time, count in both Late AND Early Out
    active_days = 0
    inactive_days = 0
    late_arrivals = 0
    early_outs = 0
    
    # Define late threshold (10:00 AM)
    late_threshold_hour = 10
    late_threshold_minute = 0
    
    for record in attendance_records:
        status = record.get("status", "")
        check_in = record.get("check_in", "")
        
        # Check if login was late (after 10 AM)
        is_late_login = False
        if check_in:
            try:
                # Parse check-in time (format: "10:30 AM" or "09:15 AM")
                time_parts = check_in.upper().replace('.', ':').strip()
                if 'AM' in time_parts or 'PM' in time_parts:
                    is_pm = 'PM' in time_parts
                    time_str = time_parts.replace('AM', '').replace('PM', '').strip()
                    parts = time_str.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    
                    # Convert to 24-hour format
                    if is_pm and hour != 12:
                        hour += 12
                    elif not is_pm and hour == 12:
                        hour = 0
                    
                    # Check if late (after 10 AM)
                    if hour > late_threshold_hour or (hour == late_threshold_hour and minute > late_threshold_minute):
                        is_late_login = True
            except:
                pass
        
        # Count based on status
        if status in ["Login", "Completed", "Present"]:
            active_days += 1
            if is_late_login:
                late_arrivals += 1
        elif status in ["Absent", "NA", "Not Logged"]:
            inactive_days += 1
        elif status == "Late Login" or status == "Late":
            late_arrivals += 1
            active_days += 1
        elif status == "Early Out":
            early_outs += 1
            active_days += 1
            # If early out AND also late login, count in late as well
            if is_late_login:
                late_arrivals += 1
    
    # Get today's attendance
    today_attendance = await db.attendance.find_one({
        "employee_id": employee_id,
        "date": today_str
    }, {"_id": 0})
    
    login_time = None
    logout_time = None
    hours_today = None
    
    if today_attendance:
        login_time = today_attendance.get("check_in")
        logout_time = today_attendance.get("check_out")
        hours_today = today_attendance.get("total_hours")
    
    return {
        "employee_name": employee.get("full_name"),
        "employee_id": employee.get("emp_id"),
        "department": employee.get("department"),
        "team": employee.get("team"),
        "summary": {
            "active_days": active_days,
            "inactive_days": inactive_days,
            "late_arrivals": late_arrivals,
            "early_outs": early_outs
        },
        "today": {
            "date": today_str,
            "login_time": login_time,
            "logout_time": logout_time,
            "hours_today": hours_today,
            "is_logged_in": login_time is not None,
            "is_logged_out": logout_time is not None
        },
        "current_month": now.strftime("%B %Y")
    }

@api_router.post("/employee/clock-in")
async def employee_clock_in(current_user: dict = Depends(get_current_user)):
    """Employee self clock-in"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if not employee.get("attendance_tracking_enabled", True):
        raise HTTPException(status_code=400, detail="Attendance tracking disabled")
    
    now = get_ist_now()
    today_str = now.strftime("%d-%m-%Y")
    check_in_time = now.strftime("%I:%M %p")
    
    existing = await db.attendance.find_one({"employee_id": employee_id, "date": today_str})
    if existing and existing.get("check_in"):
        raise HTTPException(status_code=400, detail="Already clocked in today")
    
    # Determine status (Late if after 9:30 AM)
    status = "Login"
    if now.hour > 9 or (now.hour == 9 and now.minute > 30):
        status = "Late Login"
    
    attendance = Attendance(
        employee_id=employee_id,
        emp_name=employee["full_name"],
        team=employee["team"],
        department=employee["department"],
        date=today_str,
        check_in=check_in_time,
        status=status
    )
    doc = attendance.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.attendance.insert_one(doc.copy())
    
    return {"message": "Clocked in successfully", "time": check_in_time, "status": status}

@api_router.post("/employee/clock-out")
async def employee_clock_out(current_user: dict = Depends(get_current_user)):
    """Employee self clock-out"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    now = get_ist_now()
    today_str = now.strftime("%d-%m-%Y")
    check_out_time = now.strftime("%I:%M %p")
    
    attendance = await db.attendance.find_one({"employee_id": employee_id, "date": today_str}, {"_id": 0})
    if not attendance:
        raise HTTPException(status_code=404, detail="No clock-in found for today")
    if attendance.get("check_out"):
        raise HTTPException(status_code=400, detail="Already clocked out")
    
    # Calculate total hours
    try:
        check_in_str = attendance.get("check_in", "")
        check_in_dt = datetime.strptime(f"{today_str} {check_in_str}", "%d-%m-%Y %I:%M %p")
        check_out_dt = datetime.strptime(f"{today_str} {check_out_time}", "%d-%m-%Y %I:%M %p")
        diff = check_out_dt - check_in_dt
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        total_hours = f"{hours}h {minutes}m"
    except:
        total_hours = None
    
    # Determine status (Early Out if before 6:00 PM)
    status = "Completed"
    if now.hour < 18:
        status = "Early Out"
    
    await db.attendance.update_one(
        {"employee_id": employee_id, "date": today_str},
        {"$set": {"check_out": check_out_time, "total_hours": total_hours, "status": status}}
    )
    
    return {"message": "Clocked out successfully", "time": check_out_time, "total_hours": total_hours, "status": status}

@api_router.get("/employee/attendance")
async def get_employee_attendance(
    duration: Optional[str] = "this_week",  # this_week, last_week, this_month, last_month, custom
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status_filter: Optional[str] = "All",
    current_user: dict = Depends(get_current_user)
):
    """Get employee's own attendance records with filters"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    now = get_ist_now()
    
    # Calculate date range based on duration
    if duration == "this_week":
        # Monday to Sunday of current week
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=6)
    elif duration == "last_week":
        start = now - timedelta(days=now.weekday() + 7)
        end = start + timedelta(days=6)
    elif duration == "this_month":
        start = now.replace(day=1)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
    elif duration == "last_month":
        first_this_month = now.replace(day=1)
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif duration == "custom" and start_date and end_date:
        start = datetime.strptime(start_date, "%d-%m-%Y")
        end = datetime.strptime(end_date, "%d-%m-%Y")
    else:
        # Default to this week
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=6)
    
    # Generate all dates in range
    records = []
    current_date = start
    while current_date <= end:
        date_str = current_date.strftime("%d-%m-%Y")
        day_name = current_date.strftime("%A")
        
        # Check if Sunday
        if day_name == "Sunday":
            record = {
                "date": date_str,
                "day": day_name,
                "login": "-",
                "logout": "-",
                "total_hours": "-",
                "status": "Sunday"
            }
        elif current_date > now:
            # Future date
            record = {
                "date": date_str,
                "day": day_name,
                "login": "-",
                "logout": "-",
                "total_hours": "-",
                "status": "NA"
            }
        else:
            # Look up actual attendance
            att = await db.attendance.find_one({
                "employee_id": employee_id,
                "date": date_str
            }, {"_id": 0})
            
            # Check for approved leave
            leave = await db.leaves.find_one({
                "employee_id": employee_id,
                "status": "approved",
                "start_date": {"$lte": current_date.strftime("%Y-%m-%d")},
                "end_date": {"$gte": current_date.strftime("%Y-%m-%d")}
            }, {"_id": 0})
            
            if leave:
                # Show leave type instead of generic "Leave"
                leave_type = leave.get("leave_type", "Leave")
                record = {
                    "date": date_str,
                    "day": day_name,
                    "login": "-",
                    "logout": "-",
                    "total_hours": "-",
                    "status": f"{leave_type} Leave"
                }
            elif att:
                # Determine display status
                display_status = "Present"
                if att.get("status") == "Late Login":
                    display_status = "Late"
                elif att.get("status") == "Early Out":
                    display_status = "Early Out"
                elif att.get("status") == "Completed":
                    display_status = "Present"
                elif att.get("status") == "Login":
                    display_status = "Present"
                
                record = {
                    "date": date_str,
                    "day": day_name,
                    "login": att.get("check_in", "-"),
                    "logout": att.get("check_out", "-"),
                    "total_hours": att.get("total_hours", "-"),
                    "status": display_status
                }
            else:
                # No attendance record - absent
                record = {
                    "date": date_str,
                    "day": day_name,
                    "login": "-",
                    "logout": "-",
                    "total_hours": "-",
                    "status": "Absent"
                }
        
        # Apply status filter
        if status_filter == "All" or record["status"] == status_filter:
            records.append(record)
        
        current_date += timedelta(days=1)
    
    return records

@api_router.get("/employee/leaves")
async def get_employee_leaves(current_user: dict = Depends(get_current_user)):
    """Get employee's leave requests and history"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    now = get_ist_now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Get all leaves for this employee
    all_leaves = await db.leaves.find({"employee_id": employee_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Separate into requests (future/current) and history (past)
    requests = []
    history = []
    
    for leave in all_leaves:
        leave_data = serialize_doc(leave)
        # Convert date format for display
        if leave.get("start_date"):
            try:
                dt = datetime.strptime(leave["start_date"], "%Y-%m-%d")
                leave_data["display_date"] = dt.strftime("%d-%m-%Y")
            except:
                leave_data["display_date"] = leave["start_date"]
        
        if leave.get("start_date", "") >= today_str:
            requests.append(leave_data)
        else:
            history.append(leave_data)
    
    return {
        "requests": requests,
        "history": history,
        "requests_count": len(requests),
        "history_count": len(history)
    }

@api_router.post("/employee/leaves/apply")
async def apply_employee_leave(data: EmployeeLeaveCreate, current_user: dict = Depends(get_current_user)):
    """Apply for leave with optional document upload"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    employee = await db.employees.find_one({"id": employee_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Validate reason length
    if not data.reason or len(data.reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Reason must be at least 10 characters")
    
    # Parse and validate leave date
    try:
        leave_dt = datetime.strptime(data.leave_date, "%d-%m-%Y")
        start_date = leave_dt.strftime("%Y-%m-%d")
        end_date = start_date  # Single day leave
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use dd-mm-yyyy")
    
    # Validate not in past
    if leave_dt.date() < get_ist_now().date():
        raise HTTPException(status_code=400, detail="Cannot apply leave for past dates")
    
    # Create leave request
    leave = LeaveRequest(
        employee_id=employee_id,
        emp_name=employee["full_name"],
        team=employee["team"],
        department=employee["department"],
        leave_type=data.leave_type,
        start_date=start_date,
        end_date=end_date,
        duration=data.duration,
        reason=data.reason,
        status="pending"
    )
    
    doc = leave.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    # Add supporting document info if provided
    if data.supporting_document_url:
        doc['supporting_document_url'] = data.supporting_document_url
        doc['supporting_document_name'] = data.supporting_document_name
    
    await db.leaves.insert_one(doc.copy())
    
    await log_audit(current_user["id"], "apply_leave", "leave", leave.id)
    
    return {"message": "Leave request submitted successfully", "leave_id": leave.id}

@api_router.put("/employee/leaves/{leave_id}")
async def update_employee_leave(leave_id: str, data: EmployeeLeaveCreate, current_user: dict = Depends(get_current_user)):
    """Update a pending leave request"""
    if not current_user.get("employee_id"):
        raise HTTPException(status_code=404, detail="No employee profile linked")
    
    employee_id = current_user["employee_id"]
    
    # Find the leave request
    leave = await db.leaves.find_one({"id": leave_id, "employee_id": employee_id}, {"_id": 0})
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    # Can only edit pending requests
    if leave.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Can only edit pending leave requests")
    
    # Validate reason length
    if not data.reason or len(data.reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Reason must be at least 10 characters")
    
    # Parse and validate leave date
    try:
        leave_dt = datetime.strptime(data.leave_date, "%d-%m-%Y")
        start_date = leave_dt.strftime("%Y-%m-%d")
        end_date = start_date
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use dd-mm-yyyy")
    
    # Validate not in past
    if leave_dt.date() < get_ist_now().date():
        raise HTTPException(status_code=400, detail="Cannot set leave date in the past")
    
    # Update the leave request
    update_data = {
        "leave_type": data.leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "duration": data.duration,
        "reason": data.reason
    }
    
    if data.supporting_document_url:
        update_data["supporting_document_url"] = data.supporting_document_url
        update_data["supporting_document_name"] = data.supporting_document_name
    
    await db.leaves.update_one(
        {"id": leave_id},
        {"$set": update_data}
    )
    
    await log_audit(current_user["id"], "update_leave", "leave", leave_id)
    
    return {"message": "Leave request updated successfully"}

# ============== ONBOARDING ROUTES ==============

@api_router.get("/onboarding/stats")
async def get_onboarding_stats(current_user: dict = Depends(get_current_user)):
    """Get onboarding statistics for dashboard"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    total = await db.onboarding.count_documents({})
    pending = await db.onboarding.count_documents({"status": OnboardingStatus.PENDING})
    in_progress = await db.onboarding.count_documents({"status": OnboardingStatus.IN_PROGRESS})
    under_review = await db.onboarding.count_documents({"status": OnboardingStatus.UNDER_REVIEW})
    approved = await db.onboarding.count_documents({"status": OnboardingStatus.APPROVED})
    rejected = await db.onboarding.count_documents({"status": OnboardingStatus.REJECTED})
    
    # Get pending document verifications
    pending_verifications = await db.onboarding_documents.count_documents({"status": DocumentStatus.UPLOADED})
    rejected_documents = await db.onboarding_documents.count_documents({"status": DocumentStatus.REJECTED})
    
    return {
        "total_employees": total,
        "pending": pending,
        "in_progress": in_progress,
        "under_review": under_review,
        "approved": approved,
        "rejected": rejected,
        "pending_verifications": pending_verifications,
        "rejected_documents": rejected_documents,
        "completion_rate": round((approved / total * 100) if total > 0 else 0, 1)
    }

@api_router.get("/onboarding/list")
async def get_onboarding_list(
    status: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all onboarding records for HR review"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    query = {}
    if status and status != "All":
        query["status"] = status
    if department and department != "All":
        query["department"] = department
    if search:
        query["$or"] = [
            {"emp_name": {"$regex": search, "$options": "i"}},
            {"emp_id": {"$regex": search, "$options": "i"}}
        ]
    
    records = await db.onboarding.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [serialize_doc(r) for r in records]

@api_router.get("/onboarding/employee/{employee_id}")
async def get_employee_onboarding(employee_id: str, current_user: dict = Depends(get_current_user)):
    """Get onboarding status and documents for an employee"""
    # Employees can only view their own, HR can view all
    if current_user["role"] == UserRole.EMPLOYEE:
        if current_user.get("employee_id") != employee_id:
            raise HTTPException(status_code=403, detail="Permission denied")
    
    onboarding = await db.onboarding.find_one({"employee_id": employee_id}, {"_id": 0})
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    
    # Get all documents
    documents = await db.onboarding_documents.find({"employee_id": employee_id}, {"_id": 0}).to_list(20)
    
    return {
        "onboarding": serialize_doc(onboarding),
        "documents": [serialize_doc(d) for d in documents],
        "required_documents": REQUIRED_DOCUMENTS
    }

@api_router.get("/onboarding/my-status")
async def get_my_onboarding_status(current_user: dict = Depends(get_current_user)):
    """Get current user's onboarding status"""
    employee_id = current_user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee linked to this user")
    
    onboarding = await db.onboarding.find_one({"employee_id": employee_id}, {"_id": 0})
    if not onboarding:
        # Create onboarding record if doesn't exist
        employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        onboarding = OnboardingRecord(
            employee_id=employee_id,
            emp_id=employee.get("emp_id"),
            emp_name=employee.get("full_name"),
            department=employee.get("department"),
            team=employee.get("team"),
            designation=employee.get("designation")
        )
        doc = onboarding.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.onboarding.insert_one(doc.copy())
        
        # Create document placeholders
        for req_doc in REQUIRED_DOCUMENTS:
            doc_record = OnboardingDocument(
                employee_id=employee_id,
                document_type=req_doc["type"],
                document_label=req_doc["label"]
            )
            doc_data = doc_record.model_dump()
            doc_data['created_at'] = doc_data['created_at'].isoformat()
            await db.onboarding_documents.insert_one(doc_data.copy())
        
        onboarding = doc
    
    # Get documents
    documents = await db.onboarding_documents.find({"employee_id": employee_id}, {"_id": 0}).to_list(20)
    
    # Check if user is in onboarding flow
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    
    return {
        "onboarding": serialize_doc(onboarding) if isinstance(onboarding, dict) else onboarding,
        "documents": [serialize_doc(d) for d in documents],
        "required_documents": REQUIRED_DOCUMENTS,
        "is_first_login": user.get("is_first_login", True),
        "onboarding_completed": user.get("onboarding_status") == OnboardingStatus.APPROVED
    }

@api_router.post("/onboarding/upload-document")
async def upload_onboarding_document(data: DocumentUpload, current_user: dict = Depends(get_current_user)):
    """Upload a document for onboarding"""
    employee_id = current_user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee linked to this user")
    
    # Find existing document record
    doc_record = await db.onboarding_documents.find_one({
        "employee_id": employee_id,
        "document_type": data.document_type
    }, {"_id": 0})
    
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document type not found")
    
    # Update document
    update_data = {
        "file_url": data.file_url,
        "file_public_id": data.file_public_id,
        "file_name": data.file_name,
        "status": DocumentStatus.UPLOADED,
        "uploaded_at": get_ist_now().isoformat()
    }
    
    await db.onboarding_documents.update_one(
        {"employee_id": employee_id, "document_type": data.document_type},
        {"$set": update_data}
    )
    
    # Update onboarding status to in_progress
    await db.onboarding.update_one(
        {"employee_id": employee_id},
        {"$set": {"status": OnboardingStatus.IN_PROGRESS, "updated_at": get_ist_now().isoformat()}}
    )
    
    await log_audit(current_user["id"], "upload_document", "onboarding", employee_id, f"Uploaded {data.document_type}")
    
    return {"message": "Document uploaded successfully"}

@api_router.post("/onboarding/submit")
async def submit_onboarding(current_user: dict = Depends(get_current_user)):
    """Submit onboarding for HR review"""
    employee_id = current_user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee linked to this user")
    
    # Check all required documents are uploaded
    documents = await db.onboarding_documents.find({"employee_id": employee_id}, {"_id": 0}).to_list(20)
    
    required_types = [d["type"] for d in REQUIRED_DOCUMENTS if d["required"]]
    uploaded_types = [d["document_type"] for d in documents if d.get("status") in [DocumentStatus.UPLOADED, DocumentStatus.VERIFIED]]
    
    missing = [t for t in required_types if t not in uploaded_types]
    if missing:
        missing_labels = [d["label"] for d in REQUIRED_DOCUMENTS if d["type"] in missing]
        raise HTTPException(status_code=400, detail=f"Missing required documents: {', '.join(missing_labels)}")
    
    # Update onboarding status
    await db.onboarding.update_one(
        {"employee_id": employee_id},
        {"$set": {
            "status": OnboardingStatus.UNDER_REVIEW,
            "submitted_at": get_ist_now().isoformat(),
            "updated_at": get_ist_now().isoformat()
        }}
    )
    
    await log_audit(current_user["id"], "submit_onboarding", "onboarding", employee_id)
    
    return {"message": "Onboarding submitted for review"}

@api_router.post("/onboarding/verify-document")
async def verify_onboarding_document(data: DocumentVerification, current_user: dict = Depends(get_current_user)):
    """HR verifies/rejects a document"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    doc = await db.onboarding_documents.find_one({"id": data.document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if data.status not in [DocumentStatus.VERIFIED, DocumentStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    update_data = {
        "status": data.status,
        "verified_at": get_ist_now().isoformat(),
        "verified_by": current_user["id"]
    }
    
    if data.status == DocumentStatus.REJECTED:
        update_data["rejection_reason"] = data.rejection_reason
    
    await db.onboarding_documents.update_one(
        {"id": data.document_id},
        {"$set": update_data}
    )
    
    await log_audit(current_user["id"], f"verify_document_{data.status}", "onboarding", doc["employee_id"], data.document_type if hasattr(data, 'document_type') else None)
    
    return {"message": f"Document {data.status}"}

@api_router.post("/onboarding/approve/{employee_id}")
async def approve_onboarding(employee_id: str, data: OnboardingApproval, current_user: dict = Depends(get_current_user)):
    """HR approves/rejects entire onboarding"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    onboarding = await db.onboarding.find_one({"employee_id": employee_id}, {"_id": 0})
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    
    if data.status not in [OnboardingStatus.APPROVED, OnboardingStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    # Update onboarding record
    update_data = {
        "status": data.status,
        "reviewed_at": get_ist_now().isoformat(),
        "reviewed_by": current_user["id"],
        "review_notes": data.review_notes,
        "updated_at": get_ist_now().isoformat()
    }
    
    await db.onboarding.update_one({"employee_id": employee_id}, {"$set": update_data})
    
    # Update employee's onboarding status
    employee_update = {"onboarding_status": data.status, "updated_at": get_ist_now().isoformat()}
    if data.status == OnboardingStatus.APPROVED:
        employee_update["onboarding_completed_at"] = get_ist_now().isoformat()
    
    await db.employees.update_one({"id": employee_id}, {"$set": employee_update})
    
    # Update user's onboarding status
    await db.users.update_one(
        {"employee_id": employee_id},
        {"$set": {"onboarding_status": data.status, "is_first_login": False}}
    )
    
    # Send notification email
    employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if employee:
        status_text = "approved" if data.status == OnboardingStatus.APPROVED else "requires attention"
        subject = f"Onboarding {status_text.title()} - {employee.get('full_name')}"
        html = get_onboarding_status_email(
            employee.get("full_name"),
            data.status,
            data.review_notes
        )
        asyncio.create_task(send_email_notification(employee.get("official_email"), subject, html))
    
    await log_audit(current_user["id"], f"approve_onboarding_{data.status}", "onboarding", employee_id, data.review_notes)
    
    return {"message": f"Onboarding {data.status}"}

@api_router.post("/onboarding/request-reupload/{employee_id}")
async def request_document_reupload(employee_id: str, document_type: str, reason: str, current_user: dict = Depends(get_current_user)):
    """HR requests re-upload of a specific document"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    doc = await db.onboarding_documents.find_one({
        "employee_id": employee_id,
        "document_type": document_type
    }, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await db.onboarding_documents.update_one(
        {"employee_id": employee_id, "document_type": document_type},
        {"$set": {
            "status": DocumentStatus.REJECTED,
            "rejection_reason": reason,
            "verified_at": get_ist_now().isoformat(),
            "verified_by": current_user["id"]
        }}
    )
    
    # Update onboarding status back to in_progress
    await db.onboarding.update_one(
        {"employee_id": employee_id},
        {"$set": {"status": OnboardingStatus.IN_PROGRESS, "updated_at": get_ist_now().isoformat()}}
    )
    
    return {"message": "Re-upload requested"}

# ============== TICKET ROUTES ==============

@api_router.get("/tickets")
async def get_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all tickets (HR) or own tickets (employee)"""
    query = {}
    
    if current_user["role"] == UserRole.EMPLOYEE:
        query["employee_id"] = current_user.get("employee_id")
    
    if status and status != "All":
        query["status"] = status
    if priority and priority != "All":
        query["priority"] = priority
    
    tickets = await db.tickets.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [serialize_doc(t) for t in tickets]

@api_router.post("/tickets")
async def create_ticket(data: TicketCreate, current_user: dict = Depends(get_current_user)):
    """Create a new support ticket"""
    employee_id = current_user.get("employee_id")
    employee = None
    
    if employee_id:
        employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    
    ticket = Ticket(
        employee_id=employee_id or current_user["id"],
        emp_name=employee.get("full_name") if employee else current_user.get("name"),
        department=employee.get("department") if employee else current_user.get("department", "N/A"),
        subject=data.subject,
        description=data.description,
        priority=data.priority
    )
    
    doc = ticket.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.tickets.insert_one(doc.copy())
    
    await log_audit(current_user["id"], "create_ticket", "ticket", ticket.id)
    
    return serialize_doc(doc)

@api_router.put("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, status: str, resolution: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Update ticket status (HR only)"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    ticket = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    update_data = {
        "status": status,
        "updated_at": get_ist_now().isoformat()
    }
    
    if status in ["resolved", "closed"]:
        update_data["resolved_at"] = get_ist_now().isoformat()
        update_data["resolution"] = resolution
    
    await db.tickets.update_one({"id": ticket_id}, {"$set": update_data})
    
    return {"message": f"Ticket status updated to {status}"}

@api_router.get("/tickets/stats")
async def get_ticket_stats(current_user: dict = Depends(get_current_user)):
    """Get ticket statistics"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR_MANAGER]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    total = await db.tickets.count_documents({})
    open_tickets = await db.tickets.count_documents({"status": "open"})
    in_progress = await db.tickets.count_documents({"status": "in_progress"})
    resolved = await db.tickets.count_documents({"status": "resolved"})
    
    return {
        "total": total,
        "open": open_tickets,
        "in_progress": in_progress,
        "resolved": resolved
    }

# ============== AUDIT LOG ROUTES ==============

@api_router.get("/audit-logs")
async def get_audit_logs(
    resource: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs (admin only)"""
    if current_user["role"] not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    query = {}
    if resource:
        query["resource"] = resource
    if action:
        query["action"] = action
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Add user names
    for log in logs:
        user = await db.users.find_one({"id": log["user_id"]}, {"_id": 0, "name": 1})
        log["user_name"] = user.get("name") if user else "Unknown"
    
    return [serialize_doc(l) for l in logs]

# ============== EMAIL HELPERS FOR ONBOARDING ==============

def get_onboarding_status_email(emp_name: str, status: str, notes: Optional[str] = None):
    """Generate HTML email for onboarding status notification"""
    status_color = "#10b981" if status == "approved" else "#f59e0b"
    status_text = "Approved" if status == "approved" else "Requires Attention"
    
    message = "Congratulations! Your onboarding has been approved. You now have full access to the HRMS portal." if status == "approved" else "Your onboarding requires some attention. Please log in to the portal to review the feedback and make necessary updates."
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #0b1f3b; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">BluBridge HRMS</h1>
        </div>
        <div style="background: #fffdf7; padding: 30px; border: 1px solid #e5e5e5; border-top: none; border-radius: 0 0 8px 8px;">
            <h2 style="color: #0b1f3b; margin-top: 0;">Onboarding Status Update</h2>
            <p style="color: #666;">Dear {emp_name},</p>
            <p style="color: #666;">{message}</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {status_color};">
                <p style="margin: 5px 0;"><strong>Status:</strong> <span style="color: {status_color};">{status_text}</span></p>
                {f'<p style="margin: 5px 0;"><strong>Notes:</strong> {notes}</p>' if notes else ''}
            </div>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">This is an automated notification from BluBridge HRMS.</p>
        </div>
    </div>
    """

# ============== SEED DATA ==============

@api_router.post("/seed")
async def seed_database():
    # Check if already seeded
    admin_exists = await db.users.find_one({"username": "admin"})
    if admin_exists:
        # Also ensure employee user exists
        employee_user_exists = await db.users.find_one({"username": "user"})
        if not employee_user_exists:
            # Find first employee to link
            first_emp = await db.employees.find_one({"is_deleted": {"$ne": True}}, {"_id": 0})
            if first_emp:
                emp_user = User(
                    username="user",
                    email="user@blubridge.com",
                    password_hash=hash_password("user"),
                    name=first_emp.get("full_name", "Employee User"),
                    role=UserRole.EMPLOYEE,
                    employee_id=first_emp["id"],
                    department=first_emp.get("department"),
                    team=first_emp.get("team")
                )
                doc = emp_user.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.users.insert_one(doc.copy())
        return {"message": "Database already seeded"}
    
    # Create admin user
    admin = User(
        username="admin",
        email="admin@blubridge.com",
        password_hash=hash_password("admin"),
        name="System Admin",
        role=UserRole.ADMIN,
        department="Administration"
    )
    doc = admin.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.users.insert_one(doc.copy())
    
    # Create departments
    departments = [
        {"id": str(uuid.uuid4()), "name": "Research Unit", "team_count": 8},
        {"id": str(uuid.uuid4()), "name": "Support Staff", "team_count": 1},
        {"id": str(uuid.uuid4()), "name": "Business & Product", "team_count": 5}
    ]
    await db.departments.insert_many(departments)
    
    # Create teams
    teams = [
        {"id": str(uuid.uuid4()), "name": "Compiler - Auto Differentiation", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Compiler - Computation Graph", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Data", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Framework - Graph & Auto-differentiation", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Framework - parallelism", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Framework - Tensor & Ops", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Framework - Quantz", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Tokenizer", "department": "Research Unit", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Administration", "department": "Support Staff", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Product Management", "department": "Business & Product", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Sales", "department": "Business & Product", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Marketing", "department": "Business & Product", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Business Development", "department": "Business & Product", "member_count": 0},
        {"id": str(uuid.uuid4()), "name": "Customer Success", "department": "Business & Product", "member_count": 0}
    ]
    await db.teams.insert_many(teams)
    
    # Create employees with full schema
    employees_data = [
        {"full_name": "Adhitya Charan", "official_email": "adhitya.blubridge@evoplus.in", "team": "Framework - parallelism", "stars": -11, "unsafe_count": 3, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Adwaid Suresh", "official_email": "suresh.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": -2, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.SENIOR},
        {"full_name": "Amarnath V S", "official_email": "amarnath.blubridge@evoplus.in", "team": "Framework - Quantz", "stars": -5, "unsafe_count": 2, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Anuj Kumar", "official_email": "anuj.blubridge@evoplus.in", "team": "Framework - parallelism", "stars": -11, "unsafe_count": 3, "gender": "Male", "tier_level": TierLevel.JUNIOR},
        {"full_name": "Aravind P", "official_email": "aravind.blubridge@evoplus.in", "team": "Tokenizer", "stars": -5, "unsafe_count": 2, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Aravind S", "official_email": "aravinds.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": -5, "unsafe_count": 2, "gender": "Male", "tier_level": TierLevel.SENIOR},
        {"full_name": "Chaithanya", "official_email": "chaithanya.blubridge@evoplus.in", "team": "Data", "stars": 0, "unsafe_count": 0, "gender": "Female", "tier_level": TierLevel.MID},
        {"full_name": "Dinesh", "official_email": "dinesh.blubridge@evoplus.in", "team": "Framework - parallelism", "stars": 2, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.LEAD},
        {"full_name": "Gowtham", "official_email": "gowtham.blubridge@evoplus.in", "team": "Data", "stars": 5, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.SENIOR},
        {"full_name": "Gowthamkumar", "official_email": "gowthamkumar.blubridge@evoplus.in", "team": "Framework - Tensor & Ops", "stars": 3, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Grishma", "official_email": "grishma.blubridge@evoplus.in", "team": "Framework - Graph & Auto-differentiation", "stars": 1, "unsafe_count": 0, "gender": "Female", "tier_level": TierLevel.JUNIOR},
        {"full_name": "Hamza", "official_email": "hamza.blubridge@evoplus.in", "team": "Administration", "stars": 0, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Harshini", "official_email": "harshini.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": 2, "unsafe_count": 0, "gender": "Female", "tier_level": TierLevel.JUNIOR},
        {"full_name": "Jenifa", "official_email": "jenifa.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": 4, "unsafe_count": 0, "gender": "Female", "tier_level": TierLevel.MID},
        {"full_name": "Jona", "official_email": "jona.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": 1, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.SENIOR},
        {"full_name": "Kota", "official_email": "kota.blubridge@evoplus.in", "team": "Framework - Tensor & Ops", "stars": -3, "unsafe_count": 1, "gender": "Male", "tier_level": TierLevel.MID},
        {"full_name": "Pragathi V", "official_email": "pragathi.blubridge@evoplus.in", "team": "Administration", "stars": 0, "unsafe_count": 0, "gender": "Female", "tier_level": TierLevel.JUNIOR},
        {"full_name": "Suresh K", "official_email": "sureshk.blubridge@evoplus.in", "team": "Compiler - Auto Differentiation", "stars": 2, "unsafe_count": 0, "gender": "Male", "tier_level": TierLevel.LEAD},
    ]
    
    for i, emp_data in enumerate(employees_data):
        dept = "Support Staff" if emp_data["team"] == "Administration" else "Research Unit"
        emp = Employee(
            emp_id=f"EMP{str(i + 1).zfill(4)}",
            full_name=emp_data["full_name"],
            official_email=emp_data["official_email"],
            gender=emp_data.get("gender"),
            department=dept,
            team=emp_data["team"],
            designation="Software Engineer",
            tier_level=emp_data.get("tier_level", TierLevel.MID),
            date_of_joining="2024-01-15",
            employment_type=EmploymentType.FULL_TIME,
            employee_status=EmployeeStatus.ACTIVE,
            work_location=WorkLocation.OFFICE,
            stars=emp_data["stars"],
            unsafe_count=emp_data["unsafe_count"]
        )
        doc = emp.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.employees.insert_one(doc.copy())
    
    # Create sample attendance
    today = get_ist_now().strftime("%d-%m-%Y")
    employees = await db.employees.find({}, {"_id": 0}).to_list(1000)
    
    for emp in employees[:15]:
        check_in_hour = 8 + (hash(emp["id"]) % 3)
        check_in_min = hash(emp["id"]) % 60
        check_in_time = f"{str(check_in_hour).zfill(2)}:{str(check_in_min).zfill(2)} AM"
        
        att = Attendance(
            employee_id=emp["id"],
            emp_name=emp["full_name"],
            team=emp["team"],
            department=emp["department"],
            date=today,
            check_in=check_in_time,
            status="Login"
        )
        doc = att.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.attendance.insert_one(doc.copy())
    
    # Create employee user account (user/user)
    first_emp = employees[0] if employees else None
    if first_emp:
        emp_user = User(
            username="user",
            email="user@blubridge.com",
            password_hash=hash_password("user"),
            name=first_emp.get("full_name", "Employee User"),
            role=UserRole.EMPLOYEE,
            employee_id=first_emp["id"],
            department=first_emp.get("department"),
            team=first_emp.get("team")
        )
        doc = emp_user.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.users.insert_one(doc.copy())
    
    return {"message": "Database seeded successfully"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
