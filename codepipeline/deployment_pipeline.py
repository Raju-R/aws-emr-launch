#!/usr/bin/env python3

import os

from aws_cdk import (
    core,
    aws_codebuild as codebuild,
    aws_codecommit as codecommit,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_iam as iam,
    aws_kms as kms,
    aws_s3 as s3
)

DEPLOYMENT_ACCOUNT = '876929970656'
DEPLOYMENT_REGION = 'us-west-2'
CODE_COMMIT_REPOSITORY = 'AWSProServe_project_EMRLaunch'
PIPELINE_ARTIFACTS_BUCKET = 'codepipelinesharedresourc-artifactsbucket2aac5544-7c88w1xbywt5'
PIPELINE_ARTIFACTS_KEY = 'arn:aws:kms:us-west-2:876929970656:key/e5fff83f-1b47-4cb8-9307-27fdeea12a83'
CROSS_ACCOUNT_CODE_COMMIT_ROLE = 'arn:aws:iam::052886665315:role/CrossAccountCodeCommitRes-CrossAccountCodeCommitRo-1FZD9ODMJW3HY'


def create_build_spec(project_dir: str) -> codebuild.BuildSpec:
    return codebuild.BuildSpec.from_object({
        'version': '0.2',
        'env': {
            'variables': {
                'EMR_LAUNCH_EXAMPLES_VPC': os.environ['EMR_LAUNCH_EXAMPLES_VPC'],
                'EMR_LAUNCH_EXAMPLES_ARTIFACTS_BUCKET': os.environ['EMR_LAUNCH_EXAMPLES_ARTIFACTS_BUCKET'],
                'EMR_LAUNCH_EXAMPLES_LOGS_BUCKET': os.environ['EMR_LAUNCH_EXAMPLES_LOGS_BUCKET'],
                'EMR_LAUNCH_EXAMPLES_DATA_BUCKET': os.environ['EMR_LAUNCH_EXAMPLES_DATA_BUCKET'],
                'EMR_LAUNCH_EXAMPLES_KERBEROS_ATTRIBUTES_SECRET':
                    os.environ['EMR_LAUNCH_EXAMPLES_KERBEROS_ATTRIBUTES_SECRET'],
                'EMR_LAUNCH_EXAMPLES_SECRET_CONFIGS': os.environ['EMR_LAUNCH_EXAMPLES_SECRET_CONFIGS']
            }
        },
        'phases': {
            'install': {
                'runtime-versions': {
                    'python': 3.7,
                    'nodejs': 12
                },
                'commands': [
                    'npm install aws-cdk',
                    'python3 -m pip install --user pipenv',
                    "pipenv install '-e .'"
                ]
            },
            'build': {
                'commands': [
                    f'cd {project_dir}',
                    'pipenv run $(npm bin)/cdk --verbose --require-approval never deploy'
                ]
            }
        },
        'environment': {
            'buildImage': codebuild.LinuxBuildImage.UBUNTU_14_04_BASE
        }
    })


app = core.App()
stack = core.Stack(
    app, 'EMRLaunchExamplesDeploymentPipeline', env=core.Environment(
        account=DEPLOYMENT_ACCOUNT,
        region=DEPLOYMENT_REGION))

repository = codecommit.Repository.from_repository_name(
    stack, 'CodeRepository',
    CODE_COMMIT_REPOSITORY)

artifacts_key = kms.Key.from_key_arn(
    stack, 'ArtifactsKey', PIPELINE_ARTIFACTS_KEY)
artifacts_bucket = s3.Bucket.from_bucket_attributes(
    stack, 'ArtifactsBucket',
    bucket_name=PIPELINE_ARTIFACTS_BUCKET, encryption_key=artifacts_key)
cross_account_codecommit_role = iam.Role.from_role_arn(
    stack, 'CrossAccountCodeCommitRole', CROSS_ACCOUNT_CODE_COMMIT_ROLE)

source_output = codepipeline.Artifact('SourceOutput')

code_build_role = iam.Role(
    stack, 'EMRLaunchExamplesBuildRole',
    role_name='EMRLaunchExamplesBuildRole',
    assumed_by=iam.ServicePrincipal('codebuild.amazonaws.com'),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name('PowerUserAccess'),
        iam.ManagedPolicy.from_aws_managed_policy_name('IAMFullAccess')
    ],
)

pipeline = codepipeline.Pipeline(
    stack, 'Pipeline',
    artifact_bucket=artifacts_bucket, stages=[
        codepipeline.StageProps(stage_name='Source', actions=[
            codepipeline_actions.CodeCommitSourceAction(
                action_name='CodeCommit_Source',
                repository=repository,
                output=source_output,
                role=cross_account_codecommit_role,
                branch='mainline'
            )]),
        codepipeline.StageProps(stage_name='Control-Plane', actions=[
           codepipeline_actions.CodeBuildAction(
               action_name='ControlPlane_Deploy',
               project=codebuild.PipelineProject(
                   stack, 'ControlPlaneBuild',
                   build_spec=create_build_spec('examples/control_plane'),
                   role=code_build_role),
               input=source_output
           )
        ]),
        codepipeline.StageProps(stage_name='Profiles-and-Configurations', actions=[
            codepipeline_actions.CodeBuildAction(
                action_name='EMRProfiles_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'EMRProfilesBuild',
                    build_spec=create_build_spec('examples/emr_profiles'),
                    role=code_build_role),
                input=source_output,
            ),
            codepipeline_actions.CodeBuildAction(
                action_name='ClusterConfigurations_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'ClusterConfigurationsBuild',
                    build_spec=create_build_spec('examples/cluster_configurations'),
                    role=code_build_role),
                input=source_output,
            ),
        ]),
        codepipeline.StageProps(stage_name='EMR-Launch-Function', actions=[
            codepipeline_actions.CodeBuildAction(
                action_name='EMRLaunchFunction_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'EMRLaunchFunctionBuild',
                    build_spec=create_build_spec('examples/emr_launch_function'),
                    role=code_build_role),
                input=source_output
            )
        ]),
        codepipeline.StageProps(stage_name='Pipelines', actions=[
            codepipeline_actions.CodeBuildAction(
                action_name='TransientClusterPipeline_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'TransientClusterPipelineBuild',
                    build_spec=create_build_spec('examples/transient_cluster_pipeline'),
                    role=code_build_role),
                input=source_output,
            ),
            codepipeline_actions.CodeBuildAction(
                action_name='PersistentClusterPipeline_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'PersistentClusterPipelineBuild',
                    build_spec=create_build_spec('examples/persistent_cluster_pipeline'),
                    role=code_build_role),
                input=source_output,
            ),
            codepipeline_actions.CodeBuildAction(
                action_name='SNSTriggeredPipeline_Deploy',
                project=codebuild.PipelineProject(
                    stack, 'SNSTriggeredPipelineBuild',
                    build_spec=create_build_spec('examples/sns_triggered_pipeline'),
                    role=code_build_role),
                input=source_output
            )
        ]),
    ])

cross_account_codecommit_role.grant(pipeline.role, 'sts:AssumeRole')

app.synth()