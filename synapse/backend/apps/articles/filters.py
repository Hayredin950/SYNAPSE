import django_filters

from .models import Article


class ArticleFilter(django_filters.FilterSet):
    topic = django_filters.CharFilter(lookup_expr="iexact")
    source = django_filters.UUIDFilter(field_name="source__id")
    date_from = django_filters.DateTimeFilter(
        field_name="published_at", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(
        field_name="published_at", lookup_expr="lte"
    )
    trending = django_filters.BooleanFilter(method="filter_trending")

    def filter_trending(self, queryset, name, value):
        if value:
            return queryset.filter(trending_score__gte=0.5)
        return queryset

    class Meta:
        model = Article
        fields = ["topic", "source", "date_from", "date_to", "trending"]
