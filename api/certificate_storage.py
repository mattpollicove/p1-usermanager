"""OS-specific secure certificate storage for LDAP connections.

Provides abstraction layer for storing certificates in secure OS-specific storage:
- macOS: Keychain
- Windows: Credential Manager (via keyring library)
- Linux: ~/.local/share/p1-usermanager/certs/ with restricted permissions
"""

import logging
import platform
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple
import tempfile
import os

logger = logging.getLogger(__name__)

IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'


class CertificateStorage:
    """Abstract base for OS-specific certificate storage."""
    
    @staticmethod
    def save_certificate(cert_pem: str, host: str, port: int) -> Tuple[bool, str]:
        """Save certificate to secure storage.
        
        Args:
            cert_pem: PEM-formatted certificate string
            host: Server hostname
            port: Server port
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        raise NotImplementedError
    
    @staticmethod
    def load_certificate(host: str, port: int) -> Optional[str]:
        """Load certificate from secure storage.
        
        Args:
            host: Server hostname
            port: Server port
            
        Returns:
            PEM-formatted certificate string, or None if not found
        """
        raise NotImplementedError
    
    @staticmethod
    def delete_certificate(host: str, port: int) -> Tuple[bool, str]:
        """Delete certificate from secure storage.
        
        Args:
            host: Server hostname
            port: Server port
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        raise NotImplementedError
    
    @staticmethod
    def certificate_exists(host: str, port: int) -> bool:
        """Check if certificate exists in secure storage.
        
        Args:
            host: Server hostname
            port: Server port
            
        Returns:
            True if certificate exists
        """
        raise NotImplementedError


class MacOSKeychainStorage(CertificateStorage):
    """macOS Keychain storage for certificates."""
    
    @staticmethod
    def _get_service_name(host: str, port: int) -> str:
        """Generate service name for Keychain storage."""
        return f"p1-usermanager-ldap-{host}-{port}"
    
    @staticmethod
    def _get_account_name() -> str:
        """Get account name for Keychain storage."""
        return "ldap-certificate"
    
    @staticmethod
    def save_certificate(cert_pem: str, host: str, port: int) -> Tuple[bool, str]:
        """Save certificate to macOS Keychain."""
        try:
            service = MacOSKeychainStorage._get_service_name(host, port)
            account = MacOSKeychainStorage._get_account_name()
            
            # Use security command to add certificate to Keychain
            # Store as generic password to avoid certificate parsing issues
            cmd = [
                'security', 'add-generic-password',
                '-s', service,
                '-a', account,
                '-w', cert_pem,
                '-U'  # Update if exists
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Certificate saved to Keychain for {host}:{port}")
                return True, f"Certificate saved to Keychain"
            else:
                error = result.stderr or result.stdout or "Unknown error"
                logger.error(f"Failed to save certificate to Keychain: {error}")
                return False, f"Failed to save to Keychain: {error}"
        except Exception as e:
            logger.error(f"Error saving certificate to Keychain: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    @staticmethod
    def load_certificate(host: str, port: int) -> Optional[str]:
        """Load certificate from macOS Keychain."""
        try:
            service = MacOSKeychainStorage._get_service_name(host, port)
            account = MacOSKeychainStorage._get_account_name()
            
            # Retrieve password from Keychain using -g flag
            # Note: -w returns hex-encoded data, so we use -g and parse stderr
            cmd = [
                'security', 'find-generic-password',
                '-s', service,
                '-a', account,
                '-g'  # Display password (goes to stderr in hex format)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Extract hex password from stderr: "password: 0x..."
                match = re.search(r'password: 0x([A-Fa-f0-9]+)', result.stderr)
                if match:
                    hex_password = match.group(1)
                    try:
                        cert_pem = bytes.fromhex(hex_password).decode('ascii')
                        logger.debug(f"Certificate loaded from Keychain for {host}:{port}")
                        return cert_pem if cert_pem else None
                    except (ValueError, UnicodeDecodeError) as e:
                        logger.error(f"Failed to decode certificate from hex: {e}")
                        return None
                else:
                    logger.debug(f"Could not parse password from Keychain response for {host}:{port}")
                    return None
            else:
                logger.debug(f"Certificate not found in Keychain for {host}:{port}")
                return None
        except Exception as e:
            logger.debug(f"Error loading certificate from Keychain: {e}")
            return None
    
    @staticmethod
    def delete_certificate(host: str, port: int) -> Tuple[bool, str]:
        """Delete certificate from macOS Keychain."""
        try:
            service = MacOSKeychainStorage._get_service_name(host, port)
            account = MacOSKeychainStorage._get_account_name()
            
            cmd = [
                'security', 'delete-generic-password',
                '-s', service,
                '-a', account
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Certificate deleted from Keychain for {host}:{port}")
                return True, "Certificate deleted"
            else:
                # It's okay if it doesn't exist
                logger.debug(f"Certificate not found in Keychain for deletion: {host}:{port}")
                return True, "Certificate removed"
        except Exception as e:
            logger.error(f"Error deleting certificate from Keychain: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def certificate_exists(host: str, port: int) -> bool:
        """Check if certificate exists in Keychain."""
        try:
            service = MacOSKeychainStorage._get_service_name(host, port)
            account = MacOSKeychainStorage._get_account_name()
            
            cmd = [
                'security', 'find-generic-password',
                '-s', service,
                '-a', account
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


class WindowsCredentialManagerStorage(CertificateStorage):
    """Windows Credential Manager storage for certificates (via keyring)."""
    
    @staticmethod
    def _get_service_name(host: str, port: int) -> str:
        """Generate service name for Credential Manager."""
        return f"p1-usermanager-ldap-{host}-{port}"
    
    @staticmethod
    def _get_account_name() -> str:
        """Get account name."""
        return "ldap-certificate"
    
    @staticmethod
    def save_certificate(cert_pem: str, host: str, port: int) -> Tuple[bool, str]:
        """Save certificate to Windows Credential Manager."""
        try:
            import keyring
            
            service = WindowsCredentialManagerStorage._get_service_name(host, port)
            account = WindowsCredentialManagerStorage._get_account_name()
            
            keyring.set_password(service, account, cert_pem)
            logger.info(f"Certificate saved to Credential Manager for {host}:{port}")
            return True, "Certificate saved to Credential Manager"
        except ImportError:
            logger.error("keyring library not installed. Install with: pip install keyring")
            return False, "keyring library not installed"
        except Exception as e:
            logger.error(f"Failed to save certificate to Credential Manager: {e}")
            return False, f"Failed to save: {str(e)}"
    
    @staticmethod
    def load_certificate(host: str, port: int) -> Optional[str]:
        """Load certificate from Windows Credential Manager."""
        try:
            import keyring
            
            service = WindowsCredentialManagerStorage._get_service_name(host, port)
            account = WindowsCredentialManagerStorage._get_account_name()
            
            cert_pem = keyring.get_password(service, account)
            if cert_pem:
                logger.debug(f"Certificate loaded from Credential Manager for {host}:{port}")
            else:
                logger.debug(f"Certificate not found in Credential Manager for {host}:{port}")
            return cert_pem
        except Exception as e:
            logger.debug(f"Error loading certificate from Credential Manager: {e}")
            return None
    
    @staticmethod
    def delete_certificate(host: str, port: int) -> Tuple[bool, str]:
        """Delete certificate from Windows Credential Manager."""
        try:
            import keyring
            
            service = WindowsCredentialManagerStorage._get_service_name(host, port)
            account = WindowsCredentialManagerStorage._get_account_name()
            
            keyring.delete_password(service, account)
            logger.info(f"Certificate deleted from Credential Manager for {host}:{port}")
            return True, "Certificate deleted"
        except keyring.errors.PasswordDeleteError:
            # It's okay if it doesn't exist
            logger.debug(f"Certificate not found in Credential Manager for deletion: {host}:{port}")
            return True, "Certificate removed"
        except Exception as e:
            logger.error(f"Error deleting certificate from Credential Manager: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def certificate_exists(host: str, port: int) -> bool:
        """Check if certificate exists in Credential Manager."""
        try:
            import keyring
            
            service = WindowsCredentialManagerStorage._get_service_name(host, port)
            account = WindowsCredentialManagerStorage._get_account_name()
            
            cert = keyring.get_password(service, account)
            return cert is not None
        except Exception:
            return False


class LinuxFileStorage(CertificateStorage):
    """Linux file-based storage with restricted permissions."""
    
    @staticmethod
    def _get_certs_dir() -> Path:
        """Get certificates directory with XDG Base Directory support."""
        # Try XDG_DATA_HOME first
        xdg_data = os.environ.get('XDG_DATA_HOME')
        if xdg_data:
            certs_dir = Path(xdg_data) / 'p1-usermanager' / 'certs'
        else:
            # Fall back to ~/.local/share
            certs_dir = Path.home() / '.local' / 'share' / 'p1-usermanager' / 'certs'
        
        return certs_dir
    
    @staticmethod
    def _get_cert_path(host: str, port: int) -> Path:
        """Get path to certificate file."""
        certs_dir = LinuxFileStorage._get_certs_dir()
        filename = f"{host.replace('.', '_')}_{port}.pem"
        return certs_dir / filename
    
    @staticmethod
    def save_certificate(cert_pem: str, host: str, port: int) -> Tuple[bool, str]:
        """Save certificate to ~/.local/share with restricted permissions."""
        try:
            cert_path = LinuxFileStorage._get_cert_path(host, port)
            
            # Create directory if it doesn't exist
            cert_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write certificate with restricted permissions
            cert_path.write_text(cert_pem)
            
            # Set permissions to 600 (read/write for owner only)
            cert_path.chmod(0o600)
            
            logger.info(f"Certificate saved to {cert_path} with restricted permissions")
            return True, f"Certificate saved to {cert_path}"
        except Exception as e:
            logger.error(f"Failed to save certificate: {e}")
            return False, f"Failed to save: {str(e)}"
    
    @staticmethod
    def load_certificate(host: str, port: int) -> Optional[str]:
        """Load certificate from file."""
        try:
            cert_path = LinuxFileStorage._get_cert_path(host, port)
            
            if cert_path.exists():
                cert_pem = cert_path.read_text()
                logger.debug(f"Certificate loaded from {cert_path}")
                return cert_pem
            else:
                logger.debug(f"Certificate not found at {cert_path}")
                return None
        except Exception as e:
            logger.debug(f"Error loading certificate: {e}")
            return None
    
    @staticmethod
    def delete_certificate(host: str, port: int) -> Tuple[bool, str]:
        """Delete certificate file."""
        try:
            cert_path = LinuxFileStorage._get_cert_path(host, port)
            
            if cert_path.exists():
                cert_path.unlink()
                logger.info(f"Certificate deleted from {cert_path}")
                return True, "Certificate deleted"
            else:
                logger.debug(f"Certificate not found for deletion: {cert_path}")
                return True, "Certificate removed"
        except Exception as e:
            logger.error(f"Error deleting certificate: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def certificate_exists(host: str, port: int) -> bool:
        """Check if certificate file exists."""
        try:
            cert_path = LinuxFileStorage._get_cert_path(host, port)
            return cert_path.exists()
        except Exception:
            return False


def get_certificate_storage() -> CertificateStorage:
    """Get the appropriate certificate storage backend for the current OS.
    
    Returns:
        CertificateStorage implementation for the current platform
    """
    if IS_MACOS:
        return MacOSKeychainStorage()
    elif IS_WINDOWS:
        return WindowsCredentialManagerStorage()
    elif IS_LINUX:
        return LinuxFileStorage()
    else:
        # Fallback to file-based storage
        logger.warning(f"Unknown OS: {platform.system()}, using file-based storage")
        return LinuxFileStorage()
