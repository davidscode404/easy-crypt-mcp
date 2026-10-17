# EasyCrypt + MCP server in one image.
#
# Base: EasyCrypt's own CI build image (Debian, OCaml, all opam deps, Alt-Ergo/Z3/CVC5,
# why3 already configured). We only compile EasyCrypt itself (~5-10 min) and add Python.
# Prover binaries in the base are x86_64-only, so the image is amd64 (runs under
# Rosetta/QEMU on Apple Silicon).
#
# If the base image can't be pulled, build it from EasyCrypt's repo instead (slow, ~1h):
#   git clone https://github.com/EasyCrypt/easycrypt && \
#   docker build --platform linux/amd64 --target build -t ec-build-box easycrypt/scripts/docker
#   docker build --platform linux/amd64 --build-arg BASE=ec-build-box -t easycrypt-mcp .

ARG BASE=ghcr.io/easycrypt/ec-build-box:main
FROM --platform=linux/amd64 ${BASE}

# Pin to a commit for a reproducible demo, e.g. --build-arg EC_REF=<sha>
ARG EC_REF=main

RUN opam pin add -n easycrypt "https://github.com/EasyCrypt/easycrypt.git#${EC_REF}" \
 && opam install -y easycrypt \
 && opam clean \
 && opam exec -- easycrypt why3config \
 && opam exec -- easycrypt config

# Fail the build now, not on stage, if the `llm` subcommand doesn't behave as server.py expects.
RUN printf 'lemma t : true.\nproof. trivial. qed.\n' > /tmp/Ok.ec \
 && printf 'lemma t : false.\nproof. trivial. qed.\n' > /tmp/Bad.ec \
 && cd /tmp && opam exec -- easycrypt llm -lastgoals Ok.ec \
 && { opam exec -- easycrypt llm -lastgoals Bad.ec; test $? -eq 1; } \
 && rm -f /tmp/Ok.* /tmp/Bad.*

RUN pip3 install --user --break-system-packages --no-cache-dir "mcp>=1.2" fastapi uvicorn

COPY --chown=charlie:root easycrypt_core.py mcp_server.py http_api.py /app/

ENV EASYCRYPT_BIN=easycrypt \
    PYTHONUNBUFFERED=1

# `opam exec --` puts easycrypt and the provers on PATH for whatever command runs.
ENTRYPOINT ["opam", "exec", "--"]
CMD ["python3", "/app/mcp_server.py"]