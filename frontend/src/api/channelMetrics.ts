import request from '@/utils/request';

export function trackChannelVisit(source: string) {
  return request.post('/v1/channel-metrics/visit', { source });
}
