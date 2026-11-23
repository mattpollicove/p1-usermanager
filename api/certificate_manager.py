"""Certificate management utilities for LDAP and Database connections.

This module provides unified certificate handling for both LDAP and Database
connection types, including:
- Format detection (PEM, DER, PKCS#12, etc.)
- Type detection (signed vs self-signed)
- Certificate information extraction
- Validation and warning generation
"""

import os
from pathlib import Path
from typing import Tuple, Dict, List, Optional
from datetime import datetime
import logging

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
except ImportError:
    x509 = None
    default_backend = None
    serialization = None

logger = logging.getLogger(__name__)


class CertificateManager:
    """Unified certificate management for LDAP and Database connections."""

    @staticmethod
    def detect_certificate_format(cert_path: str) -> str:
        """
        Detect certificate file format.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Format string: "PEM", "DER", "PKCS12"
            
        Raises:
            ValueError: If format cannot be detected
        """
        if not cert_path or not cert_path.strip():
            raise ValueError("Certificate path is empty")
        
        path = Path(cert_path)
        if not path.exists():
            raise ValueError(f"Certificate file not found: {cert_path}")
        
        try:
            cert_data = path.read_bytes()
        except Exception as e:
            raise ValueError(f"Cannot read certificate file: {str(e)}")
        
        # Try PEM format (text)
        if b'-----BEGIN' in cert_data:
            if b'-----BEGIN CERTIFICATE-----' in cert_data:
                return "PEM"
            elif b'-----BEGIN PKCS12-----' in cert_data or b'-----BEGIN RSA PRIVATE KEY-----' in cert_data:
                return "PEM"
        
        # Try DER format (binary)
        try:
            x509.load_der_x509_certificate(cert_data, default_backend())
            return "DER"
        except Exception:
            pass
        
        # Try PKCS#12 format
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            pkcs12.load_key_and_certificates(cert_data, None, backend=default_backend())
            return "PKCS12"
        except Exception:
            pass
        
        # Try PEM again (fallback)
        try:
            x509.load_pem_x509_certificate(cert_data, default_backend())
            return "PEM"
        except Exception:
            pass
        
        raise ValueError(f"Unknown certificate format: {cert_path}")

    @staticmethod
    def detect_certificate_type(cert_path: str) -> Tuple[str, Dict]:
        """
        Analyze certificate to determine type and extract information.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Tuple of (format_type, cert_info_dict) where cert_info_dict contains:
            - format: 'PEM'|'DER'|'PKCS12'
            - subject: Certificate subject (e.g., 'CN=Company CA')
            - issuer: Certificate issuer
            - is_self_signed: Boolean
            - valid_from: datetime when certificate becomes valid
            - valid_until: datetime when certificate expires
            - is_expired: Boolean
            - days_until_expiry: Integer (negative if expired)
            - fingerprint_sha256: Certificate fingerprint
            
        Raises:
            ValueError: If certificate cannot be parsed
        """
        if not x509 or not default_backend:
            raise ValueError("cryptography library not available")
        
        path = Path(cert_path)
        cert_data = path.read_bytes()
        format_type = CertificateManager.detect_certificate_format(cert_path)
        
        cert = None
        
        # Load certificate based on format
        if format_type == "PEM":
            try:
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except Exception as e:
                raise ValueError(f"Cannot parse PEM certificate: {str(e)}")
        
        elif format_type == "DER":
            try:
                cert = x509.load_der_x509_certificate(cert_data, default_backend())
            except Exception as e:
                raise ValueError(f"Cannot parse DER certificate: {str(e)}")
        
        elif format_type == "PKCS12":
            try:
                from cryptography.hazmat.primitives.serialization import pkcs12
                private_key, cert, additional_certs = pkcs12.load_key_and_certificates(
                    cert_data, None, backend=default_backend()
                )
                if cert is None:
                    raise ValueError("No certificate found in PKCS#12 file")
            except Exception as e:
                raise ValueError(f"Cannot parse PKCS#12 certificate: {str(e)}")
        
        if cert is None:
            raise ValueError(f"Cannot load certificate: {cert_path}")
        
        # Extract certificate information
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        is_self_signed = subject == issuer
        valid_from = cert.not_valid_before
        valid_until = cert.not_valid_after
        
        # Calculate expiration
        now = datetime.utcnow()
        is_expired = now > valid_until
        days_until_expiry = (valid_until - now).days
        
        # Calculate fingerprint
        fingerprint = cert.fingerprint(x509.hashes.SHA256())
        fingerprint_hex = fingerprint.hex().upper()
        fingerprint_formatted = ':'.join(fingerprint_hex[i:i+2] for i in range(0, len(fingerprint_hex), 2))
        
        return format_type, {
            'format': format_type,
            'subject': subject,
            'issuer': issuer,
            'is_self_signed': is_self_signed,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'is_expired': is_expired,
            'days_until_expiry': days_until_expiry,
            'fingerprint_sha256': fingerprint_formatted,
        }

    @staticmethod
    def get_certificate_warnings(cert_info: Dict) -> List[str]:
        """
        Generate warning messages for certificate.
        
        Args:
            cert_info: Dictionary from detect_certificate_type()
            
        Returns:
            List of warning message strings (empty if no warnings)
        """
        warnings = []
        
        if not cert_info:
            return warnings
        
        if cert_info.get('is_self_signed'):
            warnings.append("⚠️ Self-signed certificate")
            warnings.append("Not recommended for production use")
        
        if cert_info.get('is_expired'):
            warnings.append("✗ Certificate is EXPIRED")
        
        elif cert_info.get('days_until_expiry', 999) < 30:
            days = cert_info.get('days_until_expiry', 0)
            if days > 0:
                warnings.append(f"⚠️ Certificate expires in {days} days")
        
        return warnings

    @staticmethod
    def validate_certificate_for_ldap(cert_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Full validation pipeline for LDAP certificate.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Tuple of (is_valid, error_message, cert_info)
            - is_valid: True if certificate is valid and can be used
            - error_message: Error description if not valid
            - cert_info: Certificate information dict or None if invalid
        """
        if not cert_path or not cert_path.strip():
            return True, "", None
        
        path = Path(cert_path)
        
        # Check file exists
        if not path.exists():
            return False, f"Certificate file not found: {cert_path}", None
        
        # Check file is readable
        try:
            with open(path, 'rb') as f:
                cert_data = f.read()
            if not cert_data:
                return False, "Certificate file is empty", None
        except Exception as e:
            return False, f"Cannot read certificate file: {str(e)}", None
        
        # Detect format
        try:
            format_type = CertificateManager.detect_certificate_format(cert_path)
        except Exception as e:
            return False, f"Unknown certificate format: {str(e)}", None
        
        # Detect type and extract info
        try:
            format_type, cert_info = CertificateManager.detect_certificate_type(cert_path)
        except Exception as e:
            return False, f"Cannot parse certificate: {str(e)}", None
        
        # Check expiration (error, not warning)
        if cert_info.get('is_expired'):
            return False, "Certificate is expired", cert_info
        
        return True, "", cert_info

    @staticmethod
    def validate_certificate_for_database(
        cert_path: str, driver: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Full validation pipeline for Database certificate.
        
        Args:
            cert_path: Path to certificate file
            driver: Database driver type (optional, for driver-specific validation)
            
        Returns:
            Tuple of (is_valid, error_message, cert_info)
        """
        # For database, same validation as LDAP
        return CertificateManager.validate_certificate_for_ldap(cert_path)

    @staticmethod
    def certificate_to_config(cert_path: Optional[str]) -> Optional[str]:
        """
        Sanitize certificate path for storage in config.
        
        Args:
            cert_path: Certificate path to sanitize
            
        Returns:
            Absolute path string or None
        """
        if not cert_path:
            return None
        
        try:
            path = Path(cert_path).resolve()
            return str(path)
        except Exception:
            return None

    @staticmethod
    def certificate_from_config(cert_path: Optional[str]) -> Optional[str]:
        """
        Restore certificate path from config with validation.
        
        Args:
            cert_path: Certificate path from config
            
        Returns:
            Validated path string or None if path doesn't exist
        """
        if not cert_path:
            return None
        
        try:
            path = Path(cert_path)
            if path.exists():
                return str(path)
        except Exception:
            pass
        
        return None

    @staticmethod
    def get_certificate_info_display(cert_info: Optional[Dict]) -> str:
        """
        Format certificate information for display in UI.
        
        Args:
            cert_info: Certificate information dict
            
        Returns:
            Formatted string with certificate details
        """
        if not cert_info:
            return ""
        
        lines = []
        
        # Certificate type
        if cert_info.get('is_self_signed'):
            type_line = "⚠️ Self-Signed Certificate"
        else:
            type_line = "✓ CA-Signed Certificate"
        lines.append(type_line)
        
        # Format
        if cert_info.get('format'):
            lines.append(f"Format: {cert_info['format']}")
        
        # Subject
        if cert_info.get('subject'):
            subject = cert_info['subject']
            # Truncate if too long
            if len(subject) > 60:
                subject = subject[:57] + "..."
            lines.append(f"Subject: {subject}")
        
        # Issuer
        if cert_info.get('issuer'):
            issuer = cert_info['issuer']
            # Truncate if too long
            if len(issuer) > 60:
                issuer = issuer[:57] + "..."
            lines.append(f"Issuer: {issuer}")
        
        # Validity
        if cert_info.get('valid_until'):
            valid_until = cert_info['valid_until']
            if hasattr(valid_until, 'strftime'):
                valid_until_str = valid_until.strftime("%Y-%m-%d")
            else:
                valid_until_str = str(valid_until)
            
            days = cert_info.get('days_until_expiry', 0)
            if days > 0:
                lines.append(f"Expires: {valid_until_str} ({days} days remaining)")
            elif days == 0:
                lines.append(f"Expires: {valid_until_str} (TODAY)")
            else:
                lines.append(f"Expires: {valid_until_str} (EXPIRED {abs(days)} days ago)")
        
        return "\n".join(lines)
