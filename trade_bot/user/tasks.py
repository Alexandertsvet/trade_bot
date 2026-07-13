from celery import shared_task


@shared_task
def save_data_post_order(order):

    print("from task")

    print(order)

    print("==================")
