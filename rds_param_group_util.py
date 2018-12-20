#!/usr/bin/env python3

# Copyright (c) 2018, Justin D Holcomb (opensource@justinholcomb.me)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

################################################################################
#                                 Script Info                                  #
################################################################################

# Title:                    rds_param_group_util.py
# Author:                   Justin Holcomb
# Created:                  December 18, 2018
# Version:                  0.0.3
# Source/Inspiration:       https://gist.github.com/phill-tornroth/f0ef50f9402c7c94cbafd8c94bbec9c9
# Requires:                 Python 3.6+ (fstrings)
#                           boto3 module
# Assumes:                  AWS credentials are environment vars or supplied
#                           outside of this script.
# Description:              Compares/diffs two parameter groups.
#                           Copies a RDS parameter group.
#                           Merges one parameter group into another.

################################################################################
#                                Import Modules                                #
################################################################################

from os import environ
from sys import argv
import argparse

import boto3

################################################################################
#                                  Variables                                   #
################################################################################

default_source_region = environ['AWS_DEFAULT_REGION']
argparse_description = """
Cross AWS region capable for any action.

Compares two parameter groups and displays the differences, similar to diff.
OR
Copies a parameter group to a new destination.
OR
Merges parameters differences from the source parameter group to the destination
parameter group. Any parameter that does not exist in the destination is copied.
Any parameter that is different between the two is copied from the source OVER
the destination.
"""

################################################################################
#                                  Functions                                   #
################################################################################

def append_if_value_present(list_to_append, eval_append):
    """
    Checks to see if the "ParameterValue" key is present in the 'eval_append' dict.
    """
    if "ParameterValue" in eval_append:
        list_to_append.append(eval_append)


def change_list_to_dict(list_to_convert, key):
    """
    Changes a list into a dictionary using the 'key' parameter as the dictionary keyself.

    Assumes the key is in each dictionary.

    Assumes the key is unique.
    """

    dict_to_export = {}

    for each_obj_in_list in list_to_convert:

        # Check if key already exists in dictionary.
        if key in dict_to_export.keys():
            raise Exception(f"This key name is not unique.")

        dict_to_export[each_obj_in_list[key]] = each_obj_in_list

    return dict_to_export


def chunks(sequence, chunk_size):
    """
    Yields the sequence as a sequence of sequences size in chunk_size (or fewer,
    in the case of the last chunk). Guarantees delivery of everything (as
    opposed to strategies that leave elements off of the end when:
    len(sequence) % chunk_size != 0
    """

    start = 0
    while start < len(sequence):
        end = start + chunk_size
        yield sequence[start : start + chunk_size]
        start = end


def copy_rds_parameters(source_rds_client_obj, source_param_group, dest_rds_client_obj, dest_param_group):
    """
    Copies a parameter group.
    """

    # Construct variables
    source_summary = source_rds_client_obj.describe_db_parameter_groups(DBParameterGroupName=source_param_group)
    source_family = source_summary["DBParameterGroups"][0]["DBParameterGroupFamily"]
    source_description = source_summary["DBParameterGroups"][0]["Description"]
    source_parameters = return_all_modifiable_parameters_with_value_from_parameter_group(source_rds_client_obj, source_param_group)
    groups_in_dest_region = return_parameter_groups(dest_rds_client_obj)

    # Error if 'dest_param_group' already exists.
    if dest_param_group in groups_in_dest_region:
        raise ValueError(f"This group ({dest_param_group}) already exists in region.")

    print(f"Created {dest_param_group}:")
    print(f"  Number of 'source_parameters' to set: {len(source_parameters)}")

    # Create an origin trail of the parameter group.
    aws_tag = [
        {
            'Key': 'CopiedFrom',
            'Value': source_summary["DBParameterGroups"][0]['DBParameterGroupArn']
        },
        {
            'Key': 'CopiedUsingCmd',
            'Value': " ".join(argv)
        },
        {
            'Key': 'Repo',
            'Value': 'github.com/EpiJunkie/aws_rds_parameter_groups_utility'
        }
    ]

    # Create destination parameter group.
    dest_rds_client_obj.create_db_parameter_group(
        DBParameterGroupName=dest_param_group,
        DBParameterGroupFamily=source_family,
        Description=source_description,
        Tags=aws_tag
    )

    # Apply changes to parameter group from the base DBParameterGroupFamily values.
    post_parameters_to_group(dest_rds_client_obj, dest_param_group, source_parameters)

    print("Complete.")


def compare_rds_parameters(source_rds_client_obj, source_param_group, dest_rds_client_obj, dest_param_group, return_list=False):
    """
    Compares two parameters group for differences.
    """

    # Construct variables
    diff_list = []
    source_summary = source_rds_client_obj.describe_db_parameter_groups(DBParameterGroupName=source_param_group)
    source_family = source_summary["DBParameterGroups"][0]["DBParameterGroupFamily"]
    source_parameters = return_all_parameters_from_parameter_group(source_rds_client_obj, source_param_group)
    dest_summary = dest_rds_client_obj.describe_db_parameter_groups(DBParameterGroupName=dest_param_group)
    dest_family = dest_summary["DBParameterGroups"][0]["DBParameterGroupFamily"]
    dest_parameters = return_all_parameters_from_parameter_group(dest_rds_client_obj, dest_param_group)

    print(f"Comparing {source_param_group} and {dest_param_group}")
    print(f"    Number of 'source_parameters' to compare: {len(source_parameters)}")
    print(f"    Number of 'dest_parameters' to compare:   {len(dest_parameters)}")

    # Notify that the 'DBParameterGroupFamily' don't match as it will be indicative of many differences in the compare.
    if source_family != dest_family:
        print(f"    DBParameterGroupFamily mismatch.")
        print(f"        Source DBParameterGroupFamily:      {source_family}")
        print(f"        Destination DBParameterGroupFamily: {dest_family}")
    else:
        print(f"    DBParameterGroupFamily: {source_family}")

    print("")
    print("")
    print("diff like comparison:")
    print(f"< Source parameter group name:      {source_param_group}")
    print(f"> Destination parameter group name: {dest_param_group}")

    # Convert list to dictionaries to lookup by key ('ParameterName').
    source_parameters = change_list_to_dict(source_parameters, "ParameterName")
    dest_parameters = change_list_to_dict(dest_parameters, "ParameterName")

    # Compare source to dest, delete mutuals keys from 'dest_parameters' as compared is processed.
    for param_name, param_value in source_parameters.items():
        if param_name not in dest_parameters.keys():
            print(f"{param_name}:")
            print(f"< {source_parameters[param_name]}")
            append_if_value_present(diff_list, source_parameters[param_name])
        elif source_parameters[param_name] != dest_parameters[param_name]:
            print(f"{param_name}:")
            print(f"< {source_parameters[param_name]}")
            print(f"> {dest_parameters[param_name]}")
            append_if_value_present(diff_list, source_parameters[param_name])

            # Delete from dict to prevent showing on the second compare.
            del dest_parameters[param_name]

    # Show remaining dest parameters that do not exist in the source parameters.
    for param_name, param_value in dest_parameters.items():
        if param_name not in source_parameters.keys():
            print(f"{param_name}:")
            print(f"> {dest_parameters[param_name]}")

    print("")
    print("")

    # Future use for merge function.
    if return_list == False:
        print("Complete.")
    else:
        return diff_list


def merge_rds_parameters(source_rds_client_obj, source_param_group, dest_rds_client_obj, dest_param_group):
    """
    Merges parameters differences from the source parameter group to the destination parameter group.

    Any parameter that does not exist in the destination is copied.

    Any parameter that is different between the two is copied from the source over the destination.
    """

    parameters_diff = compare_rds_parameters(source_rds_client_obj, source_param_group, dest_rds_client_obj, dest_param_group, return_list=True)
    print(f"Merging differences from '{source_param_group}' into '{dest_param_group}'.")
    post_parameters_to_group(dest_rds_client_obj, dest_param_group, parameters_diff)


def post_parameters_to_group(rds_client_obj, param_group, parameters):
    """
    Modifies the parameters in a parameter group and post in 20x chunks.
    """

    # Return if there are no parameters
    if len(parameters) == 0:
        return

    # Posts changes to AWS using 20 parameters chunks due to API limit.
    for parameter_chunk in chunks(parameters, 20):

        # Modified Parameter Group.
        rds_client_obj.modify_db_parameter_group(DBParameterGroupName=param_group, Parameters=parameter_chunk)

        # Print parameters
        for p in parameter_chunk:
            print(f"    {p['ParameterName']} = {p['ParameterValue']}")


def return_parameter_groups(rds_client_obj):
    """
    Returns all the parameter groups in a region.
    """

    groups_to_return = []
    pagination_token = None

    # Iterate through all parameters in parameter group and break out when appropriate.
    while(True):

        # Returns when last iteration "Marker" was missing, otherwise retrieves parameters.
        if pagination_token == False:
            break
        elif pagination_token == None:
            group_chunk = rds_client_obj.describe_db_parameter_groups()
        else:
            group_chunk = rds_client_obj.describe_db_parameter_groups(Marker=pagination_token)

        # Iterate through each parameter group name.
        for g in group_chunk["DBParameterGroups"]:
            groups_to_return.append(g["DBParameterGroupName"])

        # Boto3 returns a field "Marker" when the returned parameter groups have been paginated. If missing, time to return function.
        if "Marker" in group_chunk:
            pagination_token = group_chunk['Marker']
        else:
            pagination_token = False

    return groups_to_return


def return_all_modifiable_parameters_with_value_from_parameter_group(rds_client_obj, param_group):
    """
    Returns all the modifiable parameters that have a value to set.
    """
    all_parameters = return_all_parameters_from_parameter_group(rds_client_obj, param_group)
    parameters_to_return = []

    # Iterate through each parameter.
    for p in all_parameters:

        # Only modifiable parameters ('IsModifiable' == True) with a settable value ('ParameterValue').
        if p["IsModifiable"]:
            append_if_value_present(parameters_to_return, p)

    return parameters_to_return


def return_all_parameters_from_parameter_group(rds_client_obj, param_group):
    """
    Returns all the parameters for a parameter group.
    """

    parameters_to_return = []
    pagination_token = None

    # Iterate through all parameters in parameter group and break out when appropriate.
    while(True):

        # Returns when last iteration "Marker" was missing, otherwise retrieves parameters.
        if pagination_token == False:
            break
        elif pagination_token == None:
            param_chunk = rds_client_obj.describe_db_parameters(DBParameterGroupName=param_group)
        else:
            param_chunk = rds_client_obj.describe_db_parameters(DBParameterGroupName=param_group, Marker=pagination_token)

        # Iterate over the returned parameters.
        for p in param_chunk['Parameters']:
            parameters_to_return.append(p)

        # Boto3 returns a field "Marker" when the returned parameters have been paginated. If missing, time to return function.
        if "Marker" in param_chunk:
            pagination_token = param_chunk['Marker']
        else:
            pagination_token = False

    return parameters_to_return

################################################################################
#                                     Main                                     #
################################################################################

if __name__ == "__main__":
    ''' When manually ran from command line. '''

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=argparse_description)
    parser.add_argument('-a', '--action',
                       help='Action to take.',
                       choices=['compare', 'copy', 'diff', 'merge'],
                       required=True,
                       type=str)
    parser.add_argument('-p', '--parameter-group',
                       help='Source parameter group.',
                       dest='source_param_group',
                       required=True,
                       type=str)
    parser.add_argument('-s', '--source-region',
                       help=f"Source region of parameter group. Default: {default_source_region}",
                       dest='source_region',
                       default=default_source_region,
                       type=str)
    parser.add_argument('-d', '--dest-parameter-group',
                       help='Destination parameter group.',
                       dest='dest_param_group',
                       required=True,
                       type=str)
    parser.add_argument('-w', '--dest-region',
                       help='Destination region of parameter group.',
                       dest='dest_region',
                       type=str)
    args = parser.parse_args()

    # Assume the dest AWS region is the same as the source if not given.
    if args.dest_region is None:
        args.dest_region = args.source_region

    # Create boto objects
    source_client = boto3.client("rds", region_name=args.source_region)
    dest_client = boto3.client("rds", region_name=args.dest_region)

    # Execute.
    if args.action == "compare" or args.action == "diff":
        compare_rds_parameters(source_client, args.source_param_group, dest_client, args.dest_param_group)
    elif args.action == "copy":
        copy_rds_parameters(source_client, args.source_param_group, dest_client, args.dest_param_group)
    elif args.action == "merge":
        merge_rds_parameters(source_client, args.source_param_group, dest_client, args.dest_param_group)
