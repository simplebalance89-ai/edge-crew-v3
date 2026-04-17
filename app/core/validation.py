"""
Edge Crew v3.0 - Input Validation
SQL injection detection, XSS sanitization, and validated request models
"""

import re
import html
import logging
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("edge-crew-v3.validation")

# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",  # Basic SQL meta-characters
    r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",  # Equals + SQL chars
    r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",  # OR variations
    r"((\%27)|(\'))union",  # UNION
    r"exec(\s|\+)\(s\)pux",  # EXEC/SP_
    r"\bSELECT\b",     # SELECT
    r"\bUPDATE\b",      # UPDATE
    r"UNION\s+SELECT",  # UNION SELECT
    r"INSERT\s+INTO",  # INSERT INTO
    r"DELETE\s+FROM",  # DELETE FROM
    r"DROP\s+TABLE",  # DROP TABLE
    r"ALTER\s+TABLE",  # ALTER TABLE
    r";\s*SHUTDOWN",  # SHUTDOWN
    r";\s*DROP",  # ;DROP
    r"--",  # Comment
    r"/\*",  # Block comment start
    r"\*/",  # Block comment end
    r"xp_cmdshell",  # xp_cmdshell
    r"sp_executesql",  # sp_executesql
    r"INFORMATION_SCHEMA",  # INFORMATION_SCHEMA
    r"sys\.tables",  # sys.tables
    r"sys\.columns",  # sys.columns
]

# Compiled regex for SQL injection detection
_sql_injection_regex = re.compile(
    "|".join(SQL_INJECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)

# XSS patterns
_XSS_EVENT_HANDLERS = [
    "onabort", "onactivate", "onafterprint", "onafterupdate", "onbeforeactivate",
    "onbeforecopy", "onbeforecut", "onbeforedeactivate", "onbeforeeditfocus",
    "onbeforepaste", "onbeforeprint", "onbeforeunload", "onbeforeupdate",
    "onblur", "onbounce", "oncellchange", "onchange", "onclick",
    "oncontextmenu", "oncontrolselect", "oncopy", "oncut", "ondataavailable",
    "ondatasetchanged", "ondatasetcomplete", "ondblclick", "ondeactivate",
    "ondrag", "ondragend", "ondragleave", "ondragenter", "ondragover",
    "ondrop", "ondragstart", "ondragdrop", "onerror", "onerrorupdate",
    "onfilterchange", "onfinish", "onfocus", "onfocusin", "onfocusout",
    "onhelp", "onkeydown", "onkeypress", "onkeyup", "onlayoutcomplete",
    "onload", "onlosecapture", "onmousedown", "onmouseenter", "onmouseleave",
    "onmousemove", "onmouseout", "onmouseover", "onmouseup", "onmousewheel",
    "onmove", "onmoveend", "onmovestart", "onpaste", "onpropertychange",
    "onreadystatechange", "onreset", "onresize", "onresizeend", "onresizestart",
    "onrowenter", "onrowexit", "onrowsdelete", "onrowsinserted", "onscroll",
    "onselect", "onselectionchange", "onselectstart", "onstart", "onstop",
    "onsubmit", "onunload", "onzoom",
]

# Script tag pattern
_script_tag_regex = re.compile(r"<script[^>]*>[\s\S]*?</script>", re.IGNORECASE)
# Event handler pattern
_event_handler_regex = re.compile(
    r"\s*(" + "|".join(_XSS_EVENT_HANDLERS) + r")\s*=\s*['\"]?[^'\"\s>]*",
    re.IGNORECASE,
)
# javascript: protocol pattern
_js_protocol_regex = re.compile(r"javascript:", re.IGNORECASE)
# data: URI pattern for images/scripts
_data_uri_regex = re.compile(r"data:text/html", re.IGNORECASE)


def contains_sql_injection(value: str) -> bool:
    """Check if a string contains potential SQL injection patterns"""
    if not value or not isinstance(value, str):
        return False
    
    # Check against compiled regex
    if _sql_injection_regex.search(value):
        logger.warning(f"SQL injection pattern detected in input: {value[:50]}...")
        return True
    
    return False


def sanitize_xss(value: str) -> str:
    """Sanitize a string to prevent XSS attacks"""
    if not value or not isinstance(value, str):
        return value
    
    original = value
    
    # Remove script tags
    value = _script_tag_regex.sub("", value)
    
    # Remove event handlers
    value = _event_handler_regex.sub("", value)
    
    # Remove javascript: protocol
    value = _js_protocol_regex.sub("", value)
    
    # Remove dangerous data URIs
    value = _data_uri_regex.sub("", value)
    
    # HTML escape remaining content
    value = html.escape(value)
    
    if value != original:
        logger.debug("XSS sanitization applied to input")
    
    return value


def validate_no_sql_injection(value: str) -> str:
    """Pydantic validator helper: reject SQL injection attempts"""
    if contains_sql_injection(value):
        raise ValueError("Input contains potentially dangerous SQL patterns")
    return value


def validate_and_sanitize(value: str) -> str:
    """Validate and sanitize a string input"""
    value = validate_no_sql_injection(value)
    value = sanitize_xss(value)
    return value


class ValidatedRequest(BaseModel):
    """Base model for all validated requests with automatic sanitization"""
    
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }
    
    @field_validator("*", mode="before")
    @classmethod
    def sanitize_string_fields(cls, value):
        """Automatically sanitize all string fields"""
        if isinstance(value, str):
            # Check for SQL injection first
            if contains_sql_injection(value):
                raise ValueError("Input contains potentially dangerous SQL patterns")
            # Then sanitize for XSS
            return sanitize_xss(value)
        return value


class TeamQueryRequest(ValidatedRequest):
    """Validated request for team profile queries"""
    team_name: str = Field(..., min_length=1, max_length=100, description="Team name to query")
    sport: str = Field(..., min_length=2, max_length=20, description="Sport code (NBA, NFL, MLB, etc.)")
    odds_key: Optional[str] = Field(default="", max_length=50, description="Odds API key for the league")
    opponent_name: Optional[str] = Field(default="", max_length=100, description="Opponent team name")
    
    @field_validator("sport")
    @classmethod
    def validate_sport(cls, v: str) -> str:
        """Validate sport is a known code"""
        allowed_sports = {
            "NBA", "NFL", "MLB", "NHL", "NCAAB", "NCAAF",
            "SOCCER", "MMA", "BOXING", "GOLF", "TENNIS"
        }
        v_upper = v.upper().strip()
        if v_upper not in allowed_sports:
            raise ValueError(f"Unsupported sport: {v}. Allowed: {', '.join(sorted(allowed_sports))}")
        return v_upper


class GradeRequest(ValidatedRequest):
    """Validated request for grading endpoints"""
    game_id: str = Field(..., min_length=1, max_length=100, description="Unique game identifier")
    sport: str = Field(..., min_length=2, max_length=20, description="Sport code")
    home_team: str = Field(..., min_length=1, max_length=100, description="Home team name")
    away_team: str = Field(..., min_length=1, max_length=100, description="Away team name")
    spread: Optional[float] = Field(default=None, description="Point spread")
    total: Optional[float] = Field(default=None, description="Over/under total")
    ml_home: Optional[int] = Field(default=None, description="Home team moneyline")
    ml_away: Optional[int] = Field(default=None, description="Away team moneyline")
    
    @field_validator("sport")
    @classmethod
    def validate_sport(cls, v: str) -> str:
        """Validate sport is a known code"""
        allowed_sports = {
            "NBA", "NFL", "MLB", "NHL", "NCAAB", "NCAAF",
            "SOCCER", "MMA", "BOXING", "GOLF", "TENNIS"
        }
        v_upper = v.upper().strip()
        if v_upper not in allowed_sports:
            raise ValueError(f"Unsupported sport: {v}. Allowed: {', '.join(sorted(allowed_sports))}")
        return v_upper
    
    @field_validator("spread", "total")
    @classmethod
    def validate_numeric_ranges(cls, v: Optional[float]) -> Optional[float]:
        """Validate numeric betting lines are within reasonable ranges"""
        if v is not None and abs(v) > 1000:
            raise ValueError("Betting line value is unreasonably large")
        return v


class AdminStatsRequest(ValidatedRequest):
    """Validated request for admin statistics queries"""
    start_date: Optional[str] = Field(default=None, max_length=10, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, max_length=10, description="End date (YYYY-MM-DD)")
    sport: Optional[str] = Field(default=None, max_length=20, description="Filter by sport")
    
    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format"""
        if v is None:
            return v
        import datetime
        try:
            datetime.datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v


class LoginRequest(ValidatedRequest):
    """Validated request for user login"""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)


class PickRequest(ValidatedRequest):
    """Validated request for placing a pick"""
    game_id: str = Field(..., min_length=1, max_length=100)
    team: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern=r"^(spread|moneyline|total)$")
    line: Optional[float] = Field(default=None)
    amount: float = Field(..., gt=0, le=10000)
    odds: int = Field(...)