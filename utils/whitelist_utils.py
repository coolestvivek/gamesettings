"""
Whitelist utilities for Mani 272
Syncs with JSON files for MITM proxy
"""
import json
import os
from datetime import datetime

class WhitelistManager:
    def __init__(self, base_path=None):
        if base_path is None:
            self.base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'whitelists')
        else:
            self.base_path = base_path
        
        self.regions = ['IND', 'ID', 'BR', 'ME', 'VN', 'TH', 'CIS', 'BD', 'PK', 'SG', 'NA', 'SAC', 'EU', 'TW']
        os.makedirs(self.base_path, exist_ok=True)
    
    def get_whitelist_file(self, region):
        """Get whitelist file path for region"""
        return os.path.join(self.base_path, f'whitelist_{region.lower()}.json')
    
    def load_whitelist(self, region):
        """Load whitelist for region"""
        file_path = self.get_whitelist_file(region)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_whitelist(self, region, data):
        """Save whitelist for region"""
        file_path = self.get_whitelist_file(region)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_uid(self, uid, region, expiry_timestamp):
        """Add UID to whitelist"""
        if region.upper() not in self.regions:
            return False
        
        whitelist = self.load_whitelist(region)
        whitelist[str(uid)] = {
            "expiry": int(expiry_timestamp),
            "region": region.upper()
        }
        self.save_whitelist(region, whitelist)
        return True
    
    def remove_uid(self, uid, region):
        """Remove UID from whitelist"""
        if region.upper() not in self.regions:
            return False
        
        whitelist = self.load_whitelist(region)
        uid_str = str(uid)
        
        if uid_str in whitelist:
            del whitelist[uid_str]
            self.save_whitelist(region, whitelist)
            return True
        return False
    
    def check_uid(self, uid, region):
        """Check if UID is whitelisted and not expired"""
        whitelist = self.load_whitelist(region)
        uid_str = str(uid)
        
        if uid_str in whitelist:
            data = whitelist[uid_str]
            expiry_timestamp = data.get('expiry', data) if isinstance(data, dict) else data
            current_timestamp = int(datetime.now().timestamp())
            
            if current_timestamp < expiry_timestamp:
                return True, expiry_timestamp
            else:
                # Remove expired UID
                self.remove_uid(uid, region)
                return False, None
        
        return False, None
    
    def get_all_uids(self, region):
        """Get all active UIDs for region"""
        whitelist = self.load_whitelist(region)
        current_timestamp = int(datetime.now().timestamp())
        
        active_uids = {}
        expired_uids = []
        
        for uid, data in whitelist.items():
            expiry = data.get('expiry', data) if isinstance(data, dict) else data
            if current_timestamp < expiry:
                active_uids[uid] = expiry
            else:
                expired_uids.append(uid)
        
        # Clean up expired UIDs
        for uid in expired_uids:
            self.remove_uid(uid, region)
        
        return active_uids
    
    def cleanup_expired(self):
        """Clean up all expired UIDs across all regions"""
        cleaned_count = 0
        for region in self.regions:
            whitelist = self.load_whitelist(region)
            current_timestamp = int(datetime.now().timestamp())
            
            expired_uids = []
            for uid, data in whitelist.items():
                expiry = data.get('expiry', data) if isinstance(data, dict) else data
                if current_timestamp >= expiry:
                    expired_uids.append(uid)
            
            for uid in expired_uids:
                self.remove_uid(uid, region)
                cleaned_count += 1
        
        return cleaned_count
