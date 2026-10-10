# Sensei prompts

These files are the local source for Sensei prompts and instructions. Each project has its own prompt folder under the Sensei S3 prefix:

```text
sensei/infra/prompts/sensei/context.md
sensei/infra/prompts/sensei/<project>/actions/review.md
sensei/infra/prompts/sensei/<project>/context.md

s3://hive/sensei/context.md
s3://hive/sensei/<project>/actions/review.md
s3://hive/sensei/<project>/context.md
```

The running agent reads the S3 objects, not this directory directly. Keep each project’s review prompt and context together when publishing it.
