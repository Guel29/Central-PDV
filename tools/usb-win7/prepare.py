"""Prepare immutable upstream sources. Does not build, sign or install a driver."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

UPSTREAM = 'https://github.com/cezanne/usbip-win.git'
COMMIT = '44063583a5c3e20ec459bddadc9aae37f73bda10'


def git(*args):
    return subprocess.check_output(['git', *map(str, args)], stderr=subprocess.PIPE)


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    actual = git('-C', source, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    if actual != COMMIT:
        raise ValueError('Source HEAD does not match the pinned Windows 7 revision')
    # Export the committed tree, never local files, ignored files or credentials.
    archive = git('-C', source, 'archive', '--format=tar', COMMIT)
    if destination.exists():
        raise FileExistsError('Destination already exists; preserve it and choose a fresh path')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Extract fully before exposing a usable output directory.
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        root = Path(tmp) / 'source'
        root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter='data')
        hashes = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob('*')) if p.is_file()}
        manifest = {'upstream':UPSTREAM, 'commit':COMMIT,
                    'status':'SOURCE_ONLY_NOT_SIGNED_NOT_INSTALLABLE', 'sha256':hashes}
        (root/'smartpdv-source.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        root.rename(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Optional checkout at the exact pinned revision')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.source:
            result = prepare(args.source, args.output)
        else:
            with tempfile.TemporaryDirectory(prefix='smartpdv-usb-source-') as tmp:
                source = Path(tmp)/'upstream'
                git('clone', '--no-checkout', UPSTREAM, source)
                git('-C', source, 'checkout', '--detach', COMMIT)
                result = prepare(source, args.output)
        print(f'Prepared {len(result["sha256"])} source files at {COMMIT}. NOT compiled or installable.')
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        # No raw Git diagnostics, proxy credentials or environment dumps.
        parser.exit(1, f'Source preparation failed: {type(exc).__name__}\n')


if __name__ == '__main__':
    main()
