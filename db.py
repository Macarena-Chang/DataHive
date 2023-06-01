from sqlalchemy.orm import Session
from models import UserTable, UserIn, UserOut

from sqlalchemy.exc import IntegrityError
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import UserTable, File, UserFile
def get_user(db: Session, username: str):
    return db.query(UserTable).filter(UserTable.username == username).first()

""" def create_user(db: Session, user: UserIn):
    hashed_password = get_password_hash(user.password)
    db_user = UserTable(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        disabled=user.disabled
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or Email already registered") 
    return db_user.to_dict() """

def add_file_to_user(db: Session, user_id: str, file_id: str):
    # Check if the file with the provided file_id exists in the database
    file = db.query(File).filter(File.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check if the user has already been assigned the file
    user_file = db.query(UserFile).filter(UserFile.user_id == user_id, UserFile.file_id == file_id).first()
    if user_file:
        raise HTTPException(status_code=400, detail="File already assigned to the user")

    db_user_file = UserFile(user_id=user_id, file_id=file_id)
    db.add(db_user_file)
    db.commit()

    return {"detail": "File added to user"}


def get_user_files(db: Session, user_id: str):
    user_files = db.query(UserFile).filter(UserFile.user_id == user_id).all()
    return {"file_ids": [uf.file_id for uf in user_files]}

def create_file_db(db: Session, user_id: int, file_name: str):
    # Create the File
    new_file = File(file_name=file_name)
    db.add(new_file)
    db.commit()
    
    # Get the file_id of the newly created file
    file_id = new_file.file_id

    # Assign the File to a User
    user_file = UserFile(user_id=user_id, file_id=file_id)
    db.add(user_file)
    db.commit()