#!/usr/bin/env python
import os
import sys

# Add backend to path
sys.path.insert(0, '/home/hayredin/Documents/synapse/backend')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'

import django
django.setup()

from apps.articles.models import Article, UserArticle
from apps.users.models import User
from datetime import datetime, timezone, timedelta

# Get user
user = User.objects.get(email='rino44296@gmail.com')

print("=== DATA STATUS ===")
print(f"Total Articles: {Article.objects.count()}")
print(f"UserArticle links for {user.email}: {UserArticle.objects.filter(user=user).count()}")

# Check articles from last 12 hours (since last run at 19:33)
twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
recent_articles = Article.objects.filter(scraped_at__gte=twelve_hours_ago)
print(f"\nArticles in last 12 hours: {recent_articles.count()}")

if recent_articles.count() > 0:
    print("\n=== Recent Articles (should have UserArticle links) ===")
    for a in recent_articles.order_by('-scraped_at')[:10]:
        has_link = UserArticle.objects.filter(user=user, article=a).exists()
        status = "✓ LINKED" if has_link else "✗ NOT LINKED"
        print(f"[{status}] {a.scraped_at.strftime('%H:%M')} | {a.title[:50]}...")
else:
    print("\nNo articles scraped in last 12 hours!")
    print("\n=== Last 5 Articles (oldest first to see gap) ===")
    for a in Article.objects.order_by('-scraped_at')[:5]:
        print(f"{a.scraped_at.strftime('%Y-%m-%d %H:%M')} | {a.title[:50]}...")
