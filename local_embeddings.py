"""Fixed, hash-pinned MiniLM ONNX inference; never loads remote Python/config code."""
from pathlib import Path
from functools import lru_cache
import hashlib,os,shutil,tarfile,tempfile,threading
import numpy as np

URL='https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz'
ARCHIVE_SHA='913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3'
FILES={'model.onnx':'4f148ba8ae9c2c7fbee4af2b132db8d06c6a6545b47fc83bbb98c3d22b8393e6',
       'tokenizer.json':'da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0'}
LOCK=threading.RLock()

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def model_files():
    folder=Path(os.getenv('HF_HOME',str(Path.home()/'.cache/study-desk')))/'minilm-l6-v2'
    if all((folder/name).is_file() and digest(folder/name)==sha for name,sha in FILES.items()):return folder
    folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='minilm-',dir=folder) as temporary:
        archive=Path(temporary)/'model.tar.gz'
        legacy=Path.home()/'.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx.tar.gz'
        if legacy.is_file() and digest(legacy)==ARCHIVE_SHA:shutil.copyfile(legacy,archive)
        else:
            import httpx
            with httpx.stream('GET',URL,timeout=90,follow_redirects=False) as response:
                response.raise_for_status();size=0
                with archive.open('wb') as out:
                    for block in response.iter_bytes(1024*1024):
                        size+=len(block)
                        if size>128*1024*1024:raise ValueError('Embedding model exceeds its download limit.')
                        out.write(block)
        if digest(archive)!=ARCHIVE_SHA:raise ValueError('Embedding model failed its integrity check.')
        with tarfile.open(archive,'r:gz') as bundle:
            for name,sha in FILES.items():
                member=bundle.getmember('onnx/'+name)
                if not member.isfile() or not 0<member.size<128*1024*1024:raise ValueError('Invalid embedding artifact.')
                target=Path(temporary)/name
                with bundle.extractfile(member) as source,target.open('wb') as out:shutil.copyfileobj(source,out)
                if digest(target)!=sha:raise ValueError('Embedding artifact failed its integrity check.')
                os.replace(target,folder/name)
    return folder

@lru_cache(maxsize=1)
def runtime():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    folder=model_files();tokenizer=Tokenizer.from_file(str(folder/'tokenizer.json'))
    tokenizer.enable_truncation(max_length=256);tokenizer.enable_padding(pad_id=0,pad_token='[PAD]',length=256)
    options=ort.SessionOptions();options.log_severity_level=3
    options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(folder/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    return tokenizer,session

def embed(documents):
    if not documents:return np.empty((0,384),dtype=np.float32)
    result=[]
    with LOCK:
        tokenizer,session=runtime()
        for start in range(0,len(documents),32):
            tokens=tokenizer.encode_batch(documents[start:start+32])
            ids=np.asarray([t.ids for t in tokens],dtype=np.int64)
            mask=np.asarray([t.attention_mask for t in tokens],dtype=np.int64)
            hidden=session.run(None,{'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)})[0]
            weights=np.broadcast_to(mask[:,:,None],hidden.shape)
            values=(hidden*weights).sum(1)/np.maximum(weights.sum(1),1e-9)
            values/=np.maximum(np.linalg.norm(values,axis=1,keepdims=True),1e-12)
            result.append(values.astype(np.float32))
    return np.concatenate(result)

class Encoder:
    def __call__(self,documents):return embed(documents)
