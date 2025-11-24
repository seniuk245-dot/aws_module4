import boto3
import botocore
import os
import time
import uuid

REGION = "us-east-1"
AMI_ID = "ami-0fa3fe0fa7920f68e"
INSTANCE_TYPE = "t2.micro"
BUCKET_PREFIX = "seniuk-mod4" 


def create_key_pair(ec2_client, key_name):
    """
    Створює ключову пару для EC2 та зберігає приватний ключ у файл .pem
    """
    try:
        print(f"[+] Створення key pair '{key_name}'...")
        key_pair = ec2_client.create_key_pair(KeyName=key_name)
        private_key = key_pair["KeyMaterial"]

        filename = f"{key_name}.pem"
        with os.fdopen(os.open(filename, os.O_WRONLY | os.O_CREAT, 0o400), "w+") as handle:
            handle.write(private_key)

        print(f"[OK] Ключову пару створено. Файл: {filename}")
        return filename
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            print(f"[!] Key pair '{key_name}' вже існує в AWS. Використовуємо її.")
            return f"{key_name}.pem"
        else:
            print("[ERR] Помилка при створенні key pair:", e)
            raise


def create_s3_bucket(s3_client, bucket_name):
    # Для регіону us-east-1 CreateBucketConfiguration НЕ використовується
    if REGION == "us-east-1":
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': REGION}
        )



def create_instance(ec2_client, key_name):
    """
    Створює EC2-інстанс і повертає його ID.
    """
    try:
        print(f"[+] Створення EC2 інстансу ({INSTANCE_TYPE})...")
        response = ec2_client.run_instances(
            ImageId=AMI_ID,
            MinCount=1,
            MaxCount=1,
            InstanceType=INSTANCE_TYPE,
            KeyName=key_name
        )
        instance_id = response["Instances"][0]["InstanceId"]
        print(f"[OK] Інстанс створено, ID: {instance_id}")
        return instance_id
    except botocore.exceptions.ClientError as e:
        print("[ERR] Помилка при створенні інстансу:", e)
        raise


def wait_for_instance_running(ec2_client, instance_id):
    """
    Чекає, поки інстанс перейде в стан running, і повертає його public IP.
    """
    print("[+] Очікування, поки інстанс перейде в стан 'running'...")
    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    print("[OK] Інстанс запущено.")

    reservations = ec2_client.describe_instances(InstanceIds=[instance_id])["Reservations"]
    instance = reservations[0]["Instances"][0]
    public_ip = instance.get("PublicIpAddress")
    print(f"[INFO] Public IP інстансу: {public_ip}")
    return public_ip


def terminate_instance(ec2_client, instance_id):
    """
    Завершує роботу EC2-інстансу (terminate).
    """
    try:
        print(f"[+] Термінація інстансу {instance_id}...")
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        waiter = ec2_client.get_waiter("instance_terminated")
        waiter.wait(InstanceIds=[instance_id])
        print("[OK] Інстанс успішно видалено.")
    except botocore.exceptions.ClientError as e:
        print("[ERR] Помилка при термінації інстансу:", e)


def delete_bucket_with_objects(s3_resource, bucket_name):
    """
    Видаляє всі об'єкти в бакеті, а потім сам бакет.
    """
    print(f"[+] Видалення бакету '{bucket_name}' разом з об'єктами...")
    bucket = s3_resource.Bucket(bucket_name)
    try:
        bucket.objects.all().delete()
        bucket.delete()
        print("[OK] Бакет видалено.")
    except botocore.exceptions.ClientError as e:
        print("[ERR] Помилка при видаленні бакету:", e)


def delete_key_pair(ec2_client, key_name, key_file):
    """
    Видаляє key pair з AWS та локальний .pem файл.
    """
    try:
        print(f"[+] Видалення key pair '{key_name}' з AWS...")
        ec2_client.delete_key_pair(KeyName=key_name)
        print("[OK] Key pair в AWS видалено.")
    except botocore.exceptions.ClientError as e:
        print("[ERR] Помилка при видаленні key pair в AWS:", e)

    if key_file and os.path.exists(key_file):
        print(f"[+] Видалення локального файлу ключа '{key_file}'...")
        os.remove(key_file)
        print("[OK] Локальний файл ключа видалено.")


def main():
    ec2_client = boto3.client("ec2", region_name=REGION)
    s3_client = boto3.client("s3", region_name=REGION)
    s3_resource = boto3.resource("s3", region_name=REGION)

    suffix = str(int(time.time()))
    key_name = f"mod4-key-{suffix}"
    bucket_name = f"{BUCKET_PREFIX}-{suffix}"

    print("=== AWS Module 4: автоматизація інфраструктури ===")

    key_file = create_key_pair(ec2_client, key_name)

    create_s3_bucket(s3_client, bucket_name)

    instance_id = create_instance(ec2_client, key_name)

    public_ip = wait_for_instance_running(ec2_client, instance_id)

    print("\n=== ПІДСУМОК СТВОРЕНОЇ ІНФРАСТРУКТУРИ ===")
    print(f"Key pair:        {key_name}  (файл: {key_file})")
    print(f"S3 bucket:       {bucket_name}")
    print(f"EC2 instance ID: {instance_id}")
    print(f"Public IP:       {public_ip}")
    print("==========================================\n")

    input("Натисни Enter, щоб видалити всі створені ресурси...")

    terminate_instance(ec2_client, instance_id)
    delete_bucket_with_objects(s3_resource, bucket_name)
    delete_key_pair(ec2_client, key_name, key_file)

    print("\n[FINISH] Уся інфраструктура успішно видалена.")


if __name__ == "__main__":
    main()
