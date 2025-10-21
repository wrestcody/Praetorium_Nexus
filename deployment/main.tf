# Praetorium_Nexus AWS Fargate Deployment
# This Terraform configuration sets up the necessary infrastructure to run the
# Praetorium_Nexus application as a containerized service on AWS Fargate.

# --- Provider & AWS Region ---
provider "aws" {
  region = "us-east-1" # Placeholder: Specify your target AWS region
}

# --- IAM Role for ECS Task Execution (Least Privilege) ---
# This role grants the ECS agent permissions to pull the container image
# and publish logs to CloudWatch, adhering to the principle of least privilege.
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "PraetoriumNexus_EcsTaskExecutionRole"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Attach the standard AWS-managed policy for ECS task execution.
# This policy is narrowly scoped for logging and ECR access.
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy_attachment" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# --- CloudWatch Log Group ---
# A dedicated log group for the application to store container logs for debugging and auditing.
resource "aws_cloudwatch_log_group" "nexus_log_group" {
  name = "/ecs/PraetoriumNexus"
}

# --- ECS Cluster ---
# A logical grouping for our application's services and tasks.
resource "aws_ecs_cluster" "nexus_cluster" {
  name = "PraetoriumNexusCluster"
}

# --- ECS Task Definition ---
# The blueprint for our application container. It specifies the Docker image,
# resource allocation (CPU/memory), and environment variables for secrets.
resource "aws_ecs_task_definition" "nexus_task" {
  family                   = "PraetoriumNexusTask"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"  # 0.25 vCPU
  memory                   = "512"  # 512 MiB
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_execution_role.arn # Reuse for simplicity, can be a more restrictive role

  container_definitions = jsonencode([
    {
      name      = "praetorium-nexus-container",
      image     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/praetorium-nexus:latest", # Placeholder: Replace with your ECR Image URI
      essential = true,
      portMappings = [
        {
          containerPort = 8000,
          hostPort      = 8000
        }
      ],
      # Secrets Management: Use environment variables for API keys.
      # In a production environment, this should be integrated with AWS Secrets Manager.
      environment = [
        {
          name  = "NEXUS_API_KEY",
          value = "PLACEHOLDER_NEXUS_API_KEY"
        },
        {
          name  = "VANGUARD_AGENT_API_KEY",
          value = "PLACEHOLDER_VANGUARD_AGENT_API_KEY"
        }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nexus_log_group.name,
          "awslogs-region"        = "us-east-1", # Placeholder: Must match provider region
          "awslogs-stream-prefix" = "nexus-service"
        }
      }
    }
  ])
}

# --- ECS Service ---
# This service runs and maintains a specified number of instances of the task definition,
# ensuring the application is always running.
resource "aws_ecs_service" "nexus_service" {
  name            = "PraetoriumNexusService"
  cluster         = aws_ecs_cluster.nexus_cluster.id
  task_definition = aws_ecs_task_definition.nexus_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    # Placeholder: Replace with your actual VPC subnets and security groups
    subnets         = ["subnet-0a1b2c3d4e5f67890", "subnet-0f1e2d3c4b5a69876"]
    security_groups = ["sg-0a9b8c7d6e5f43210"]
    assign_public_ip = true # Set to 'false' if using a load balancer in private subnets
  }

  # Optional: Uncomment to attach the service to a load balancer
  # load_balancer {
  #   target_group_arn = aws_lb_target_group.nexus_tg.arn
  #   container_name   = "praetorium-nexus-container"
  #   container_port   = 8000
  # }

  depends_on = [aws_iam_role_policy_attachment.ecs_task_execution_policy_attachment]
}
