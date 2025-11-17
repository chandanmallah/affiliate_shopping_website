from products.models import ShortURL

# Get the last 4 entries based on ID (highest = newest)
last_4 = ShortURL.objects.order_by('-id')[:4]

# Show what will be deleted
print("Deleting these entries:")
for item in last_4:
    print(f"ID: {item.id}, URL: {item.long_url[:100]}...")

# Delete them
last_4.delete()

print("✅ Successfully deleted the last 4 ShortURL records.")