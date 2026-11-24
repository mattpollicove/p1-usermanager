"""Certificate discovery and management for LDAP connections."""

import ssl
import socket
from pathlib import Path
from typing import Optional, Tuple, Dict
import logging

from api.certificate_storage import get_certificate_storage

logger = logging.getLogger(__name__)


def get_certs_directory() -> Path:
    """Get or create the certificates directory (legacy fallback)."""
    certs_dir = Path(__file__).parent.parent / "certs"
    certs_dir.mkdir(exist_ok=True)
    return certs_dir


def retrieve_server_certificate(host: str, port: int = 636) -> Optional[str]:
    """Retrieve SSL certificate from LDAP server.
    
    Args:
        host: LDAP server hostname
        port: LDAP server port (default 636 for LDAPS)
        
    Returns:
        PEM-formatted certificate string, or None if retrieval fails
    """
    try:
        # Create SSL context that doesn't verify the certificate
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to server and retrieve certificate
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert_der = ssock.getpeercert(binary_form=True)
                if cert_der:
                    # Convert DER to PEM format
                    import base64
                    # Encode DER to base64
                    b64_cert = base64.b64encode(cert_der).decode('ascii')
                    # Add line breaks every 64 characters for proper PEM format
                    pem_lines = [b64_cert[i:i+64] for i in range(0, len(b64_cert), 64)]
                    # Build final PEM certificate
                    pem_cert = "-----BEGIN CERTIFICATE-----\n"
                    pem_cert += "\n".join(pem_lines)
                    pem_cert += "\n-----END CERTIFICATE-----\n"
                    return pem_cert
    except Exception as e:
        logger.error(f"Failed to retrieve certificate from {host}:{port}: {e}")
        return None


def save_certificate(cert_pem: str, host: str, port: int = 636) -> Tuple[bool, str]:
    """Save certificate to secure OS-specific storage.
    
    Args:
        cert_pem: PEM-formatted certificate string
        host: LDAP server hostname
        port: LDAP server port
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        storage = get_certificate_storage()
        return storage.save_certificate(cert_pem, host, port)
    except Exception as e:
        logger.error(f"Failed to save certificate: {e}")
        return False, f"Error: {str(e)}"


def load_certificate(host: str, port: int = 636) -> Optional[str]:
    """Load certificate from secure OS-specific storage.
    
    Args:
        host: LDAP server hostname
        port: LDAP server port
        
    Returns:
        PEM-formatted certificate string, or None if not found
    """
    try:
        storage = get_certificate_storage()
        return storage.load_certificate(host, port)
    except Exception as e:
        logger.error(f"Failed to load certificate: {e}")
        return None


def delete_certificate(host: str, port: int = 636) -> Tuple[bool, str]:
    """Delete certificate from secure storage.
    
    Args:
        host: LDAP server hostname
        port: LDAP server port
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        storage = get_certificate_storage()
        return storage.delete_certificate(host, port)
    except Exception as e:
        logger.error(f"Failed to delete certificate: {e}")
        return False, f"Error: {str(e)}"


def certificate_exists(host: str, port: int = 636) -> bool:
    """Check if certificate exists in secure storage.
    
    Args:
        host: LDAP server hostname
        port: LDAP server port
        
    Returns:
        True if certificate exists
    """
    try:
        storage = get_certificate_storage()
        return storage.certificate_exists(host, port)
    except Exception:
        return False


def get_certificate_fingerprint(cert_pem: str) -> Optional[str]:
    """Get SHA-256 fingerprint of certificate.
    
    Args:
        cert_pem: PEM-formatted certificate string
        
    Returns:
        Hex string fingerprint or None if parsing fails
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        import base64
        
        # Remove PEM headers and decode
        cert_data = cert_pem.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "").strip()
        cert_der = base64.b64decode(cert_data)
        
        # Load and get fingerprint
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        fingerprint = cert.fingerprint(hashes.SHA256())
        return fingerprint.hex().upper()
    except Exception as e:
        logger.error(f"Failed to get certificate fingerprint: {e}")
        return None


def parse_certificate_info(cert_pem: str) -> Optional[Dict]:
    """Parse certificate details from PEM string.
    
    Args:
        cert_pem: PEM-formatted certificate string
        
    Returns:
        Dictionary with certificate info (subject, issuer, expiration, etc.)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        import base64
        from datetime import datetime, timezone
        
        # Remove PEM headers and decode
        cert_data = cert_pem.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "").strip()
        cert_der = base64.b64decode(cert_data)
        
        # Load certificate
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        
        # Extract info
        info = {
            'subject': cert.subject.rfc4514_string(),
            'issuer': cert.issuer.rfc4514_string(),
            'not_before': cert.not_valid_before_utc.isoformat(),
            'not_after': cert.not_valid_after_utc.isoformat(),
            'is_self_signed': cert.issuer == cert.subject,
            'fingerprint': get_certificate_fingerprint(cert_pem),
        }
        
        # Check if expired
        now = datetime.now(timezone.utc)
        info['is_expired'] = now > cert.not_valid_after_utc
        
        return info
    except Exception as e:
        logger.error(f"Failed to parse certificate info: {e}")
        return None
