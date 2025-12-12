from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

def EnC_Vr(N):
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)

def DEc_Uid(H):
    n = s = 0
    for b in bytes.fromhex(H):
        n |= (b & 0x7F) << s
        s += 7
        if not (b & 0x80):
            break
    return n

def CrEaTe_VarianT(field_number, value):
    field_number = int(field_number)
    return EnC_Vr((field_number << 3) | 0) + EnC_Vr(int(value))

def CrEaTe_LenGTh(field_number, value):
    field_number = int(field_number)
    if isinstance(value, (bytes, bytearray)):
        encoded_value = bytes(value)
    elif isinstance(value, str):
        encoded_value = value.encode('latin-1', 'replace')
    else:
        encoded_value = str(value).encode()
    return EnC_Vr((field_number << 3) | 2) + EnC_Vr(len(encoded_value)) + encoded_value

def E_AEs(Pc):
    Z = bytes.fromhex(Pc) if isinstance(Pc, str) else bytes(Pc)
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    K = AES.new(key, AES.MODE_CBC, iv)
    R = K.encrypt(pad(Z, AES.block_size))
    return R

def encrypt_api(plain_text):
    if isinstance(plain_text, (bytes, bytearray)):
        plain_bytes = bytes(plain_text)
    else:
        plain_bytes = bytes.fromhex(plain_text)
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_bytes, AES.block_size))
    return cipher_text.hex()

def aes_decrypt(cipher_text):
    if isinstance(cipher_text, (bytes, bytearray)):
        cipher_bytes = bytes(cipher_text)
    else:
        cipher_bytes = bytes.fromhex(cipher_text)
    key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
    iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    if len(cipher_bytes) % AES.block_size != 0:
        cipher_bytes = pad(cipher_bytes, AES.block_size)
    decrypted = cipher.decrypt(cipher_bytes)
    try:
        return unpad(decrypted, AES.block_size)
    except ValueError:
        return decrypted
