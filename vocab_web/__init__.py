"""Serverless (Vercel) edition of the vocab-srs study tool.

The local tool in tools/vocab-srs/ keeps running unchanged on the HPC login nodes; this package
is the deployable variant whose state lives in Postgres instead of on disk.
"""
