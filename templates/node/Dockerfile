# La sortie Nitro produite par `pnpm build` est indépendante de l'architecture :
# la CI la construit une fois, l'image ne fait que la copier.
#
# CONTRAINTE MULTI-ARCH : aucune instruction RUN, sinon buildx doit émuler
# l'architecture étrangère.
FROM node:22-alpine

WORKDIR /app
COPY .output ./.output

USER node
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
