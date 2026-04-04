import calendar



def return_data_from_year(year:int):
    result = []
    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            result.append(f"{year}-{month:02d}-{day:02d}")

    return result


def return_two_element(iter_element:list):

    result = []
    for i in range(0, len(iter_element), 2):
        if i + 1 < len(iter_element):
            result.append((iter_element[i], iter_element[i + 1]))
        else:
            result.append((iter_element[i], iter_element[i]))
    return result