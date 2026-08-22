FROM glitchtip/glitchtip:6.1.6

USER root

COPY platform/observability/patch_glitchtip_schema.py /opt/iktara/patch_glitchtip_schema.py
COPY cPlatform/static/Iktara/ /opt/iktara-assets/

RUN python /opt/iktara/patch_glitchtip_schema.py && \
    rm -f /opt/iktara/patch_glitchtip_schema.py

USER app
