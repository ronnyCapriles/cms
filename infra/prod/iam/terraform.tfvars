environment      = "prod"
region           = "us-east-1"
state_bucket     = "ronnycapriles-portfolio-tfstate"
parameter_prefix = "/portfolio/prod"
allowed_subjects = [
  "repo:ronnyCapriles@64428513/cms@1351794649:ref:refs/heads/main",
  "repo:ronnyCapriles/cms:ref:refs/heads/main",
]
