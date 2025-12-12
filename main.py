from typing import List, Optional
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status 
from pydantic import BaseModel 
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey 
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Relationship
app = FastAPI()
engine = create_engine("sqlite:///./test.db", echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=create_engine)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def get_current_user():
    return User(id=1, email="chair@test.com", role="chair")
class SubmissionStatus(str, Enum):
    Submitted = "Submit"
    Accept = "accept"
    Reject = "reject"
    under_review= "under_review"
    camera_ready_submit = "camera_ready_submit"
Base = declarative_base()
class Submission(Base):
    __tablename__ = 'submission'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Integer, ForeignKey('user.id'))
    status = Column(SQLEnum(SubmissionStatus), default=SubmissionStatus.Submitted, nullable=False)
    decision_date=Column(DateTime, nullable=True)
class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    role = Column(String, default='author')
    review= Relationship("Review", back_populate= "reviewer")
def check_chair(current_user: User):
    if current_user.role != 'chair':
        raise PermissionError("You don't have permisson!")
def make_decision(db: Session, submission_id: int, decision: str, current_user: User) -> Submission:
    check_chair(current_user)
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise ValueError("Submission not found")
    decision_upper = decision.upper()
    if decision_upper == "ACCEPT":
        status = SubmissionStatus.Accept
    elif decision_upper == "REJECT": status = Submission.Reject
    else:
        raise ValueError("Invalid decision.")
    submission.status = status
    submission.decision_date = datetime.now()
    db.commit()
    db.refresh(submission)
    return submission
def get_accept_submission(db: Session, current_user: User) -> List[Submission]:
    check_chair(current_user)
    accept_list =  db.query(Submission).filter(Submission.status == Submission.Accept).all()
    return accept_list
def get_status(db: Session, submission_id: int) -> Submission:
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise LookupError("Submission not found")
    return {"id": submission.id, "status": submission.status.value}
router = APIRouter()
class DecisionRequest(BaseModel):
    submission_id: int
    decision: str
class SubmissionResponse(BaseModel):
    submission_id: int
    new_status: str
    message: str
    class Config:
        orm_mode = True
def handle_submission_decision(submission_id: int, request_body: DecisionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        update_submission = make_decision(db, submission_id, request_body.decision, current_user)
        return SubmissionResponse(submission_id = update_submission.id,new_status=update_submission.status.value,message="Decision made successfully.")
    except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
class AcceptSubmissionResponse(BaseModel):
    id: int
    title: str
    status: str
    decision_date: datetime
    class Config:
        orm_mode = True
@router.get("/submissions/accepted", response_model=List[AcceptSubmissionResponse])
def list_accepted_submissions(db: Session=Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        accept_list = get_accept_submission(db, current_user)
        return accept_list
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
class Review(Base):
    __tablename__="review"
    id =Column(Integer, primary_key= True)
    submission_id=Column(Integer, ForeignKey("submission.id"))
    review_id=Column(Integer, ForeignKey("user.id"))
    score=Column(Integer)
    comment=Column(String)
    create_at=Column(DateTime, default=datetime.utcnow)
    Submission = Relationship("Submission", back_populate="review")
    Submission = Relationship("User", back_populate="review")
def get_review(db: Session, submission_id: int):
    return db.query(Review).filter(Review.submission_id==submission_id).all()
