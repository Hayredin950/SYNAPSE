#!/usr/bin/env python
import os
import sys
sys.path.insert(0, '/home/hayredin/Documents/synapse/backend')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'

import django
django.setup()

from apps.articles.models import Article, UserArticle
from apps.users.models import User
from datetime import datetime, timezone, timedelta

u = User.objects.get(email='rino44296@gmail.com')
yesterday = datetime.now(timezone.utc) - timedelta(hours=24)

recent = Article.objects.filter(scraped_at__gte=yesterday).count()
recent_linked = UserArticle.objects.filter(user=u, article__scraped_at__gte=yesterday).count()

print(f'Articles in last 24h: {recent}')
print(f'UserArticle links in last 24h: {recent_linked}')
print(f'Total Articles: {Article.objects.count()}')
print(f'Total UserArticles: {UserArticle.objects.filter(user=u).count()}')

if recent > 0 and recent_linked == 0:
    print('\n*** PROBLEM: Articles scraped but NO UserArticle links created! ***')
    print('This confirms the bug: user_id is not reaching the database pipeline.')
