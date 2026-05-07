import bcrypt
import jwt
from datetime import timedelta, datetime, timezone
from .models import JWTPayload
import os
import copy
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class CryptContext:
    def __init__(self) -> None:
        self.is_symmetric: bool | None = None
        
        self.HASHING_ALGO = os.environ.get("HASHING_ALGO", "HS256")
        self.SECRET_TOKEN = os.environ.get("SECRET_TOKEN", None)
        self.PUBLIC_KEY = os.environ.get("PUBLIC_KEY", None)
        self.PRIVATE_KEY = os.environ.get("PRIVATE_KEY", None)
        
        self.verify_config()
    
    def verify_config(self) -> None:
        """ Verify the configurations including algorithm selection and keys """
        
        try:
            # Verify if the algorithm is supported by library
            jwt.get_algorithm_by_name(self.HASHING_ALGO)
        except (jwt.InvalidAlgorithmError, NotImplementedError, KeyError) as err:
            logger.error(f"Algorithm not supported : {self.HASHING_ALGO} \n error : {err}")
            raise
            
        if self.HASHING_ALGO.startswith("HS"):
            if not self.SECRET_TOKEN: 
                logger.error(f"Secret Token not found in the environment for algorithm : {self.HASHING_ALGO}")
                raise Exception("Unable to load secret token from the environment")
            self.is_symmetric = True
        
        else:
            if not self.PUBLIC_KEY or not self.PRIVATE_KEY:
                logger.error(f"Unable to load public/private key for Algorithm :{self.HASHING_ALGO}")
                raise Exception("Unable to load public/private key(s)")
            self.is_symmetric = False
            
            
    def get_password_hash(self, password: str) -> str:
        """ Returns password hash to be stored in DB """
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password=password.encode("utf-8"), salt=salt)
        return hash_bytes.decode("utf-8")
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """ Verify plaintext password against hased password string """
        
        password_bytes = password.encode("utf-8")
        hashed_password_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password=password_bytes, hashed_password=hashed_password_bytes)
    
    def create_access_token(self, data: JWTPayload, expire_delta: timedelta) -> str:
        """ Creates Auth token for user and return it. """
        
        payload = data.model_dump(exclude_none=True)
        payload["exp"] = datetime.now(tz=timezone.utc) + expire_delta
        
        try:
            if self.is_symmetric:
                token = jwt.encode(
                    payload=payload,
                    key=self.SECRET_TOKEN,
                    algorithm=self.HASHING_ALGO
                )
                return token
            
            else:
                token = jwt.encode(
                    payload=payload,
                    key=self.PRIVATE_KEY,
                    algorithm=self.HASHING_ALGO
                )
                return token
        except jwt.exceptions.InvalidKeyError:
            logger.error("Invalid secret/private key")
            raise
        
        except Exception as err:
            logger.error(f"Unknown error occured : \t{err}")
            raise
        
        
    def verify_and_decode_access_token(self, token: str) -> dict :
        """ Verify the access token and return payload if valid else return False """
        is_valid = False
        is_expired = True
        error = None
        payload = None
        
        if self.is_symmetric:
            decode_key = self.SECRET_TOKEN
        else:
            decode_key = self.PUBLIC_KEY
            
        try:
            raw_payload = jwt.decode(
                jwt=token,
                key=decode_key,
                algorithms=self.HASHING_ALGO
            )

            payload = JWTPayload(**raw_payload)
            is_valid = True
            is_expired = False
            
        except jwt.exceptions.ExpiredSignatureError:
            logger.critical("token expired")
            is_expired = True
            error = "Token Expired"
        except jwt.exceptions.InvalidSignatureError:
            logger.critical("Invalid token signature")
            is_valid = False
            error = "Invalid Token"
        except jwt.exceptions.DecodeError as err:
            logger.critical("Unable to decode token")
            is_valid = False
            error = str(err)
        except jwt.exceptions.InvalidTokenError as err:
            logger.error(f"Error while decoding token : \t {err}")
            raise
        except Exception as err:
            logger.error(f"Unknown Exception ocuured: \t {err}")
            raise
        
        
        return {
            "data" : payload,
            "is_expired" : is_expired,
            "is_valid" : is_valid,
            "error" : error
        }