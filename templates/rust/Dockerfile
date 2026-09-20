# Image assemblée à partir des binaires déjà cross-compilés par la CI
# (cargo-zigbuild, cibles musl statiques).
#
# CONTRAINTE MULTI-ARCH : aucune instruction RUN. Un RUN forcerait buildx à
# émuler l'architecture étrangère via QEMU, ce qui coûte 10 à 20× sur du Rust
# et annulerait tout le bénéfice de la cross-compilation.
FROM gcr.io/distroless/static-debian12:nonroot

ARG TARGETARCH
COPY dist/${TARGETARCH}/app /usr/local/bin/app

USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/app"]
