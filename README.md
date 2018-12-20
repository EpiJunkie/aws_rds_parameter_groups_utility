# aws_rds_parameter_groups_utility

Copies, compares/diffs, and merges AWS RDS [parameter groups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithParamGroups.html). This functionality is not provided by the [aws cli tools](https://aws.amazon.com/cli/) nor [Python SDK (boto3)](https://aws.amazon.com/sdk-for-python/).


- Requires:
    * Python 3.6 or later - Uses [fstring](https://www.python.org/dev/peps/pep-0498/).
        - OSX: `brew install python3`
    * [boto3](https://pypi.org/project/boto3/) module
        - To install: `python3 -m pip install --user boto3`


- Assumes:
    * AWS credentials are provided outside of the script. `direnv` is recommended, info below.


- `direnv` usage:
    * Have [`direnv`](https://direnv.net) installed.
        - Debian/Ubuntu: `sudo apt-get install direnv`
        - OSX: `brew install direnv`
    * Have the `direnv` [shell hook in your profile](https://direnv.net/index.html#setup).
    * Have copied `.envrc.default` to `.envrc` and have entered valid AWS credentials into the file.
    * Have allowed `direnv` to load the `.envrc` file once in that directory (using `direnv allow`).


## Script usage:

```
epijunkie$ cd aws_rds_parameter_groups_utility/
direnv: error .envrc is blocked. Run `direnv allow` to approve its content.
epijunkie$ direnv allow
direnv: loading .envrc
direnv: export +AWS_ACCESS_KEY_ID +AWS_DEFAULT_REGION +AWS_SECRET_ACCESS_KEY
epijunkie$
epijunkie$ ./rds_param_group_util.py -h
usage: rds_param_group_util.py [-h] -a {compare,copy,diff,merge} -p
                               SOURCE_PARAM_GROUP [-s SOURCE_REGION] -d
                               DEST_PARAM_GROUP [-w DEST_REGION]

Cross AWS region capable for any action.

Compares two parameter groups and displays the differences, similar to diff.
OR
Copies a parameter group to a new destination.
OR
Merges parameters differences from the source parameter group to the destination
parameter group. Any parameter that does not exist in the destination is copied.
Any parameter that is different between the two is copied from the source OVER
the destination.

optional arguments:
  -h, --help            show this help message and exit
  -a {compare,copy,diff,merge}, --action {compare,copy,diff,merge}
                        Action to take.
  -p SOURCE_PARAM_GROUP, --parameter-group SOURCE_PARAM_GROUP
                        Source parameter group.
  -s SOURCE_REGION, --source-region SOURCE_REGION
                        Source region of parameter group. Default: us-east-1
  -d DEST_PARAM_GROUP, --dest-parameter-group DEST_PARAM_GROUP
                        Destination parameter group.
  -w DEST_REGION, --dest-region DEST_REGION
                        Destination region of parameter group.
epijunkie$
```

