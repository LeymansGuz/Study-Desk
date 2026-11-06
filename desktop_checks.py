"""Offline release self-check for the frozen runtime; never calls an LLM."""
def run():
    import os,tempfile,json
    os.environ['ANONYMIZED_TELEMETRY']='false'
    from pathlib import Path
    root=Path(__file__).resolve().parent
    for name in ('node','opa'):
        binary=root/'bin'/(name+('.exe' if os.name=='nt' else ''))
        assert binary.is_file() and os.access(binary,os.X_OK),f'Bundled {name} is not executable'
    os.environ['STUDY_NODE_BINARY']=str(root/'bin'/('node.exe' if os.name=='nt' else 'node'))
    from math_format import validate_fields
    validate_fields((r'Half is $\frac{1}{2}$; $x^2+1$.',))
    try:validate_fields(('Invalid $x',))
    except ValueError:pass
    else:raise AssertionError('Invalid mathematical markup was not rejected.')
    from answer_parts import SolvedPart,MathClaim
    from math_checks import verify_claims
    checked=verify_claims([SolvedPart(kind='symbolic',answer='Identity',checks=[MathClaim(left='x+x',right='2*x')])])
    assert checked and checked[0]['status']=='passed',checked
    from vector_store import Client
    import sqlite3
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE VIRTUAL TABLE text_check USING fts5(body)')
        connection.execute('INSERT INTO text_check VALUES(?)',('Case-insensitive source search',))
        assert connection.execute("SELECT COUNT(*) FROM text_check WHERE text_check MATCH 'SOURCE'").fetchone()[0]==1
    with tempfile.TemporaryDirectory(prefix='study-desktop-check-',ignore_cleanup_errors=True) as tmp:
        client=Client(tmp)
        collection=client.create_collection('release_check')
        collection.add(ids=['one'],documents=['Document storage test'],embeddings=[[1.,0.,1.]])
        assert collection.query(query_embeddings=[[1.,0.,1.]],n_results=1)['ids']==[['one']]
        client.delete_collection('release_check')
    from extractous import Extractor
    text,_=Extractor().extract_bytes_to_string(bytearray(b'Study Desk document check 12345'))
    assert '12345' in text
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    image=Image.new('RGB',(520,120),'white')
    ImageDraw.Draw(image).text((20,25),'STUDY DESK 12345',fill='black',font=ImageFont.load_default(size=36))
    result,_=RapidOCR(intra_op_num_threads=1,inter_op_num_threads=1)(np.array(image))
    assert result and '12345' in ' '.join(row[1] for row in result),result
    from update_blocks import make_map,reconstruct
    with tempfile.TemporaryDirectory(prefix='study-update-check-') as tmp:
        import random
        folder=Path(tmp);raw=random.Random(13).randbytes(1024*1024)
        old=folder/'old';old.write_bytes(raw)
        target=folder/'new';target.write_bytes(b'new script'+raw)
        expected=target.read_bytes()
        stats=reconstruct(make_map(target,'0.0.1'),old,folder/'staged',lambda offset,size:expected[offset:offset+size])
        assert (folder/'staged').read_bytes()==expected and stats['reused']>len(raw)*.7
    print(json.dumps({'katex':True,'symbolic_worker':True,'vector_database':True,'office_extractor':True,'ocr':True,'differential_reconstruction':True,'provider_calls':0}))
