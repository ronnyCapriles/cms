# Passed to every root: terraform init -backend-config=../../backend.hcl
# The bucket is created by hand once; see README.md step 2.
bucket = "ronnycapriles-portfolio-tfstate"
region = "us-east-1"
