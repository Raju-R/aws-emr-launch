#!/usr/bin/env python3

from aws_cdk import (
    aws_ec2 as ec2,
    aws_s3 as s3,
    core
)

from aws_emr_launch.constructs.emr_constructs import emr_profile

app = core.App()
stack = core.Stack(app, 'EmrProfilesStack', env=core.Environment(account='876929970656', region='us-west-2'))

vpc = ec2.Vpc.from_lookup(stack, 'Vpc', vpc_id='vpc-01c3cc44009934845')

artifacts_bucket = s3.Bucket.from_bucket_name(stack, 'ArtifactsBucket', 'chamcca-emr-launch-artifacts-uw2')
logs_bucket = s3.Bucket.from_bucket_name(stack, 'LogsBucket', 'chamcca-emr-launch-logs-uw2')
data_bucket = s3.Bucket.from_bucket_name(stack, 'DataBucket', 'chamcca-emr-launch-data-uw2')

emr_profile = emr_profile.EMRProfile(
    stack, 'EMRProfile',
    profile_name='test-emr-profile',
    vpc=vpc,
    artifacts_bucket=artifacts_bucket,
    logs_bucket=logs_bucket)

emr_profile \
    .authorize_input_buckets([data_bucket]) \
    .authorize_output_buckets([data_bucket])

app.synth()