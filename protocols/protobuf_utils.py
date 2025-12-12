import json
from protobuf_decoder.protobuf_decoder import Parser
from crypto.encryption_utils import EnC_Vr, CrEaTe_VarianT, CrEaTe_LenGTh
import codecs
def _to_bytes(val):
    if isinstance(val, (bytes, bytearray)):
        return bytes(val)
    if isinstance(val, str):
        try:
            s = codecs.decode(val, "unicode_escape")
            return s.encode("latin-1", "replace")
        except Exception:
            return val.encode("utf-8", "replace")
    if isinstance(val, dict):
        return CrEaTe_ProTo(val)
    return str(val).encode()

def CrEaTe_ProTo(fields):
    if isinstance(fields, str):
        fields = json.loads(fields)
    packet = bytearray()
    for key, entry in fields.items():
        field_num = int(key)
        if isinstance(entry, dict) and "wire_type" in entry:
            wt = entry.get("wire_type")
            val = entry.get("data")
            if wt == "varint":
                packet.extend(CrEaTe_VarianT(field_num, int(val)))
            elif wt in ("string", "bytes"):
                packet.extend(CrEaTe_LenGTh(field_num, _to_bytes(val)))
            elif wt in ("length_delimited",):
                if isinstance(val, dict):
                    nested = CrEaTe_ProTo(val)
                else:
                    nested = _to_bytes(val)
                packet.extend(CrEaTe_LenGTh(field_num, nested))
            else:
                if isinstance(val, int):
                    packet.extend(CrEaTe_VarianT(field_num, int(val)))
                elif isinstance(val, dict):
                    packet.extend(CrEaTe_LenGTh(field_num, CrEaTe_ProTo(val)))
                else:
                    packet.extend(CrEaTe_LenGTh(field_num, _to_bytes(val)))
        else:
            if isinstance(entry, int):
                packet.extend(CrEaTe_VarianT(field_num, entry))
            elif isinstance(entry, dict):
                packet.extend(CrEaTe_LenGTh(field_num, CrEaTe_ProTo(entry)))
            else:
                packet.extend(CrEaTe_LenGTh(field_num, _to_bytes(entry)))
    return bytes(packet)
def parse_results(parsed_results):
    """Parse protocol buffer results"""
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type == "varint":
            field_data['data'] = result.data
        if result.wire_type == "string":
            field_data['data'] = result.data
        if result.wire_type == "bytes":
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = parse_results(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

def get_available_room(input_text):
    """Get available room from input text"""
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_objects = parsed_results
        parsed_results_dict = parse_results(parsed_results_objects)
        json_data = json.dumps(parsed_results_dict)
        return json_data
    except Exception as e:
        print(f"error {e}")
        return None