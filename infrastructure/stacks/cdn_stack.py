"""CDN Stack - CloudFront distribution with S3 origin for frontend React SPA.

- Global CDN for React SPA static assets
- S3 bucket for frontend static assets (defined here to avoid cross-stack cycles)
- Origin Access Control for secure S3 access
- HTTPS only (TLS 1.2+) per Requirement 7.2
- SPA routing: custom error responses for client-side routing
- /api/* and /health forwarded to ALB origin
- Custom domain: medical.wjmapp.com
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_certificatemanager as acm,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_elasticloadbalancingv2 as elbv2,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_s3 as s3,
)
from constructs import Construct

CUSTOM_DOMAIN = "medical.wjmapp.com"
# *.wjmapp.com certificate (us-east-1, required for CloudFront)
CERT_ARN = "arn:aws:acm:us-east-1:577823079867:certificate/b171568e-0160-407c-b4b0-276fa9b9f46e"
HOSTED_ZONE_ID = "Z09462701MQ5EKMHLOBG4"
HOSTED_ZONE_NAME = "wjmapp.com"


class CdnStack(Stack):
    """Defines CloudFront distribution with S3 origin for frontend."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        alb: elbv2.ApplicationLoadBalancer,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Frontend Static Assets Bucket
        self.frontend_bucket = s3.Bucket(
            self,
            "FrontendStaticBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html",
        )

        # ALB origin — HTTPS. CloudFront sends SNI as the ALB DNS name.
        # The ALB certificate (*.wjmapp.com) won't match the ALB DNS name,
        # so we use an HttpOrigin pointed at api.wjmapp.com (Route53 alias to ALB).
        alb_origin = origins.HttpOrigin(
            f"api.{HOSTED_ZONE_NAME}",
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
            https_port=443,
            origin_ssl_protocols=[cloudfront.OriginSslPolicy.TLS_V1_2],
        )

        # Cache policy for API: no caching
        api_cache_policy = cloudfront.CachePolicy(
            self,
            "ApiCachePolicy",
            default_ttl=Duration.seconds(0),
            min_ttl=Duration.seconds(0),
            max_ttl=Duration.seconds(0),
        )

        api_origin_request_policy = cloudfront.OriginRequestPolicy(
            self,
            "ApiOriginRequestPolicy",
            header_behavior=cloudfront.OriginRequestHeaderBehavior.all(),
            query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
            cookie_behavior=cloudfront.OriginRequestCookieBehavior.all(),
        )

        api_behavior = cloudfront.BehaviorOptions(
            origin=alb_origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
            cache_policy=api_cache_policy,
            origin_request_policy=api_origin_request_policy,
        )

        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.frontend_bucket
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True,
            ),
            additional_behaviors={
                "/api/*": api_behavior,
                "/health": api_behavior,
            },
            domain_names=[CUSTOM_DOMAIN],
            certificate=acm.Certificate.from_certificate_arn(self, "DistCert", CERT_ARN),
            default_root_object="index.html",
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_ALL,
        )

        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "HostedZone",
            hosted_zone_id=HOSTED_ZONE_ID,
            zone_name=HOSTED_ZONE_NAME,
        )

        # Route53 A alias: api.wjmapp.com → ALB (for CloudFront HTTPS origin SNI)
        route53.ARecord(
            self,
            "AlbAliasRecord",
            zone=hosted_zone,
            record_name="api",
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(alb)
            ),
        )

        # Route53 A alias: medical.wjmapp.com → CloudFront
        route53.ARecord(
            self,
            "CloudFrontAliasRecord",
            zone=hosted_zone,
            record_name="medical",
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(self.distribution)
            ),
        )
