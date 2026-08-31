def calculate_rate(price, area):
    rate = price / area
    return rate


price = 5000000
area = 1500

rate = calculate_rate(price, area)

print("Rate per sq ft:", rate)