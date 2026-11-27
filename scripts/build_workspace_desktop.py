"""Build a private x64 Windows portable beta from an allowlisted source tree."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RUNTIME_HASH="8d4d3590c10449d78aa4375f534e6d5f3027d67fdc362dd1a882279db6f90fdf"
MODULES=("workspace","workspace_reliability","workspace_chat","workspace_desktop","workspace_dpapi",
         "memory","reader_v2","claims","verification","llm_tasks","hybrid_extraction","baselines",
         "semantic","controller","data/memora")


def build(runtime,destination):
    if hashlib.sha256(runtime.read_bytes()).hexdigest()!=RUNTIME_HASH:
        raise ValueError("Expected official CPython 3.14.0 x64 embeddable ZIP")
    with TemporaryDirectory() as tmp:
        stage=Path(tmp)
        with zipfile.ZipFile(runtime) as src:
            for name in src.namelist():
                if not name.lower().startswith("vcruntime"):
                    src.extract(name,stage/"runtime")
        (stage/"runtime/python314._pth").write_text("python314.zip\n.\n..\n")
        for name in MODULES:
            rel=Path("trace_mem")/(name+".py")
            (stage/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/rel,stage/rel)
        for name in ("app.js","style.css","index.html"):
            rel=Path("trace_mem/workspace_web")/name
            (stage/rel).parent.mkdir(exist_ok=True)
            shutil.copyfile(ROOT/rel,stage/rel)
        for study in ("workspace40","workspace40b"):
            rel=Path("research")/study/"results.json"
            (stage/rel).parent.mkdir(parents=True)
            shutil.copyfile(ROOT/rel,stage/rel)
        shutil.copyfile(ROOT/"desktop/START HERE.txt",stage/"START HERE.txt")
        (stage/"THIRD PARTY.txt").write_text("CPython 3.14.0 x64 embedded distribution from python.org. See runtime/LICENSE.txt for PSF and incorporated components. The search path was configured for Workspace; VC runtime DLLs are excluded. Windows, .NET, browser and Ollama are system prerequisites. No model weights included.\n")
        csc=Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run([str(csc),"/nologo","/target:winexe","/platform:x64","/reference:System.Management.dll",
                        "/out:"+str(stage/"TRACE-Mem Workspace.exe"),str(ROOT/"desktop/Workspace.cs")],check=True)
        with zipfile.ZipFile(destination,"x",zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(stage.rglob("*")):
                if file.is_file():
                    archive.write(file,file.relative_to(stage))
    print(destination,hashlib.sha256(destination.read_bytes()).hexdigest())


if __name__=="__main__":
    build(*map(Path,sys.argv[1:]))
